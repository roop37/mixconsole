"""Service facade (order, progress, cancel, pool), settings precedence, backend plugins."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from mixconsole.analysis import registry
from mixconsole.analysis.interfaces import BeatResult
from mixconsole.cli import app
from mixconsole.config import load_settings
from mixconsole.io import write_audio
from mixconsole.service import Cancelled, CancelToken, ProgressEvent, analyze_tracks
from mixconsole.testing.synth import generate_track


@pytest.fixture(scope="module")
def files(tmp_path_factory):
    directory = tmp_path_factory.mktemp("service")
    paths = []
    for bpm in (100, 128, 140):
        audio, _ = generate_track(bpm=bpm, bars=4, seed=bpm)
        paths.append(write_audio(directory / f"{bpm}.wav", audio))
    return paths


def test_inline_order_and_progress(files, tmp_path):
    events: list[ProgressEvent] = []
    results = analyze_tracks(files, cache_dir=tmp_path, progress=events.append, workers=1)
    assert [round(r.global_bpm) for r in results] == [100, 128, 140]
    assert events[0].fraction == 0
    assert events[-1].fraction == 1
    assert [e.fraction for e in events] == sorted(e.fraction for e in events)


def test_pool_keeps_input_order(files, tmp_path):
    events: list[ProgressEvent] = []
    results = analyze_tracks(
        files,
        cache_dir=tmp_path,
        workers=3,
        progress=events.append,
        executor_factory=lambda n: ThreadPoolExecutor(max_workers=n),
    )
    assert [round(r.global_bpm) for r in results] == [100, 128, 140]
    assert events[-1].fraction == 1


def test_real_process_pool(files, tmp_path):
    results = analyze_tracks(files[:2], cache_dir=tmp_path, workers=2)
    assert [round(r.global_bpm) for r in results] == [100, 128]


def test_cancel_before_start(files, tmp_path):
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        analyze_tracks(files, cache_dir=tmp_path, cancel=token)


def test_cancel_from_progress_in_pool(files, tmp_path):
    token = CancelToken()

    def stop_after_first(event: ProgressEvent) -> None:
        if event.fraction > 0:
            token.cancel()

    with pytest.raises(Cancelled):
        analyze_tracks(
            files,
            cache_dir=tmp_path,
            workers=1 + 1,
            cancel=token,
            progress=stop_after_first,
            executor_factory=lambda n: ThreadPoolExecutor(max_workers=1),
        )


def test_settings_precedence(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('workers = 2\nmax_stretch = 0.05\n[backends]\nbeats = "librosa"\n')
    monkeypatch.setenv("MIXCONSOLE_CONFIG", str(config))
    monkeypatch.setenv("MIXCONSOLE_WORKERS", "3")
    monkeypatch.setenv("MIXCONSOLE_BACKEND_SECTIONS", "novelty")
    monkeypatch.setenv("MIXCONSOLE_OFFLINE", "yes")
    settings = load_settings()
    assert settings.workers == 3  # env beats file
    assert settings.max_stretch == 0.05  # file beats default
    assert settings.backends == {"beats": "librosa", "sections": "novelty"}
    assert settings.offline is True
    config.write_text("wokers = 2\n")  # typo must fail loudly
    monkeypatch.delenv("MIXCONSOLE_WORKERS")
    with pytest.raises(ValidationError):
        load_settings()


def test_config_show_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("MIXCONSOLE_CONFIG", str(tmp_path / "missing.toml"))
    run = CliRunner().invoke(app, ["config", "show"])
    assert run.exit_code == 0
    assert "not found, using defaults" in run.output
    assert '"max_stretch": 0.08' in run.output


class FixedBeats:
    kind = "beats"
    name = "fixed_test"
    version = "1"

    def analyze(self, features, sample_rate):
        return BeatResult([0.5, 1.0, 1.5, 2.0], [0.5], 4, 1.0)


def test_plugins_register_and_skip_broken(monkeypatch, caplog):
    good = SimpleNamespace(name="good", load=lambda: FixedBeats)

    def boom():
        raise ImportError("missing dependency")

    bad = SimpleNamespace(name="bad", load=boom)
    monkeypatch.setattr(registry, "entry_points", lambda group: [good, bad])
    monkeypatch.setattr(registry, "_plugins_loaded", False)
    try:
        assert registry.load_plugins() == ["beats=fixed_test"]
        assert "skipping backend plugin bad" in caplog.text
        assert registry.selection({"beats": "fixed_test"})["beats"] == "fixed_test"
        with pytest.raises(ValueError, match="already registered"):
            registry.register("beats", FixedBeats())
        with pytest.raises(ValueError, match="unknown backend kind"):
            registry.register("tempo", FixedBeats())
    finally:
        registry.BEATS.pop("fixed_test", None)


def test_engine_cancel_between_stages(files, tmp_path):
    from mixconsole.analysis import analyze

    token = CancelToken()
    events = []

    def report(event):
        events.append(event.stage)
        if event.stage == "features":
            token.cancel()

    with pytest.raises(Cancelled, match="cancelled"):
        analyze(files[0], cache_dir=tmp_path, progress=report, cancel=token)
    assert events == ["cache", "decode", "features"]
    assert not list(tmp_path.rglob("analysis.json"))


def test_empty_batch_worker_validation_and_progress():
    events = []
    assert analyze_tracks([], workers=1, progress=events.append) == []
    assert events[-1].fraction == 1
    for workers in (0, -1, 33):
        with pytest.raises(ValueError, match="workers"):
            analyze_tracks([], workers=workers)
    for fraction in (-0.1, 1.1, float("nan")):
        with pytest.raises(ValueError, match="fraction"):
            ProgressEvent("stage", fraction)


def test_invalid_environment_boolean_and_nested_backends(tmp_path, monkeypatch):
    monkeypatch.setenv("MIXCONSOLE_CONFIG", str(tmp_path / "missing"))
    monkeypatch.setenv("MIXCONSOLE_OFFLINE", "typo")
    with pytest.raises(ValidationError, match="boolean"):
        load_settings()
    monkeypatch.setenv("MIXCONSOLE_OFFLINE", "true")
    monkeypatch.setenv("MIXCONSOLE_BACKENDS__BEATS", "librosa")
    assert load_settings().backends == {"beats": "librosa"}


def test_cache_commands_use_toml_and_explicit_override(tmp_path, monkeypatch):
    configured = tmp_path / "configured"
    explicit = tmp_path / "explicit"
    config = tmp_path / "config.toml"
    config.write_text(f'cache_dir = "{configured.as_posix()}"\n')
    monkeypatch.setenv("MIXCONSOLE_CONFIG", str(config))
    monkeypatch.delenv("MIXCONSOLE_CACHE_DIR", raising=False)
    runner = CliRunner()
    info = runner.invoke(app, ["cache", "info"])
    assert info.exit_code == 0
    assert str(configured) in info.output
    info = runner.invoke(app, ["cache", "info", "--cache-dir", str(explicit)])
    assert info.exit_code == 0
    assert str(explicit) in info.output
    # Clearing the configured root must preserve unrelated files.
    configured.mkdir()
    unrelated = configured / "keep.txt"
    unrelated.write_text("preserve")
    cleared = runner.invoke(app, ["cache", "clear"])
    assert cleared.exit_code == 0
    assert unrelated.read_text() == "preserve"


def test_invalid_plugin_is_skipped_and_cancellation_never_falls_back(monkeypatch, caplog):
    plugin = SimpleNamespace(
        name="invalid", load=lambda: SimpleNamespace(kind="beats", name="invalid", version="1")
    )
    monkeypatch.setattr(registry, "entry_points", lambda group: [plugin])
    monkeypatch.setattr(registry, "_plugins_loaded", False)
    assert registry.load_plugins() == []
    assert "invalid" not in registry.BEATS
    assert "skipping backend plugin invalid" in caplog.text
    calls = []

    def cancelled(name):
        calls.append(name)
        raise Cancelled("stop")

    with pytest.raises(Cancelled, match="stop"):
        registry.run("beats", {"beats": "plugin"}, cancelled)
    assert calls == ["plugin"]
