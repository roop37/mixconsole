"""M4 corpus: manifest sanity, baseline systems, aggregation and the corpus runner (tiny inputs)."""

import json
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from mixconsole.bench import corpus as bc
from mixconsole.bench.results import load_results, write_latest, write_result
from mixconsole.cli import app
from mixconsole.io import SAMPLE_RATE, write_audio
from mixconsole.testing.synth import generate_track


def test_manifest_is_cc_only_and_diverse():
    manifest = bc.load_corpus()
    assert len(manifest.pairs) >= 30
    for track in manifest.tracks:
        assert track.license in ("CC0-1.0", "CC-BY-3.0", "CC-BY-4.0")
        assert track.attribution
        assert str(track.source_url).startswith("https://")
    genres = " ".join(t.genre.lower() for t in manifest.tracks)
    for word in ("house", "hip-hop", "pop", "rock", "soul", "afro", "indian", "acoustic"):
        assert word in genres
    assert {p.kind for p in manifest.pairs} == {"same-genre", "cross-genre"}
    first = [p.id for p in bc.run_order(manifest)[:3]]
    assert len(set(first)) == 3


def test_manifest_rejects_bad_pairs(tmp_path):
    path = tmp_path / "pairs.yaml"
    path.write_text(
        "tracks: []\npairs:\n- {id: x, a: nope, b: nope2, kind: same-genre}\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="unknown"):
        bc.load_corpus(path)


def test_page_license():
    assert bc.page_license("<p>CC0 1.0 Universal License</p>") == "CC0-1.0"
    assert bc.page_license("Attribution 4.0 International  License") == "CC-BY-4.0"
    assert bc.page_license("Attribution-NonCommercial 4.0 International License") is None
    assert bc.page_license("all rights reserved") is None


def _track(license_: str = "CC-BY-4.0", audio: bool = True) -> bc.CorpusTrack:
    return bc.CorpusTrack.model_validate(
        {
            "id": "t1",
            "title": "T",
            "artist": "A",
            "genre": "g",
            "license": license_,
            "source_url": "https://example.test/t1",
            "attribution": "x",
            **({"audio_url": "https://example.test/t1.mp3"} if audio else {}),
        }
    )


class _Response:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        data, self.data = self.data[:size] if size > 0 else self.data, b""
        return data


def test_fetch_verifies_license_before_download(tmp_path, monkeypatch):
    calls: list[str] = []

    def fake(request, timeout):
        calls.append(request.full_url)
        if request.full_url.endswith("t1"):
            return _Response(b"Attribution 4.0 International License")
        return _Response(b"x" * 2000)

    monkeypatch.setattr(bc, "urlopen", fake)
    path = bc.fetch_track(_track(), tmp_path)
    assert path.read_bytes() == b"x" * 2000
    assert bc.fetch_track(_track(), tmp_path) == path
    assert len(calls) == 2  # cached second time
    with pytest.raises(ValueError, match="license changed"):
        bc.fetch_track(_track("CC0-1.0"), tmp_path / "other")
    manifest = bc.Corpus(tracks=[_track("CC0-1.0")], pairs=[])
    assert "license changed" in bc.fetch_corpus(manifest, tmp_path / "third")[0]


def test_crossfade_variants():
    a, _ = generate_track(bpm=120, bars=4, seed=1)
    b, _ = generate_track(bpm=120, bars=4, seed=2)
    linear = bc.crossfade(a, b, seconds=2)
    power = bc.crossfade(a, b, seconds=2, equal_power=True)
    assert linear.length == power.length == 2 * SAMPLE_RATE
    assert len(linear.audio) == len(a) + len(b) - linear.length
    assert linear.inspection.contribution_a is not None
    # equal power keeps energy near constant, linear dips by ~3 dB in the middle
    mid = linear.length // 2
    lin_mid = np.sum(
        np.square(linear.inspection.contribution_a[mid - 99 : mid + 99])
        + np.square(linear.inspection.contribution_b[mid - 99 : mid + 99])  # pyright: ignore[reportOptionalSubscript]
    )
    pow_mid = np.sum(
        np.square(power.inspection.contribution_a[mid - 99 : mid + 99])  # pyright: ignore[reportOptionalSubscript]
        + np.square(power.inspection.contribution_b[mid - 99 : mid + 99])  # pyright: ignore[reportOptionalSubscript]
    )
    assert pow_mid > lin_mid


def test_trim_and_hard_cut_and_excerpt():
    a, _ = generate_track(bpm=120, bars=4, seed=1)
    padded = np.concatenate((a, np.zeros((SAMPLE_RATE, 2), np.float32)))
    trimmed = bc.crossfade(padded, a, seconds=1, trim=True)
    untrimmed = bc.crossfade(padded, a, seconds=1)
    assert len(trimmed.audio) < len(untrimmed.audio)
    cut = bc.hard_cut(a, a)
    assert cut.length == 0
    assert cut.seam == len(a)
    assert len(bc.centered_excerpt(a, 0, 1.0)) == SAMPLE_RATE
    assert len(bc.centered_excerpt(a, len(a), 1.0)) == SAMPLE_RATE
    assert len(bc.centered_excerpt(a[:100], 50, 1.0)) == 100
    assert bc._trim(np.zeros((10, 2), np.float32), head=True).shape == (10, 2)  # pyright: ignore[reportPrivateUsage]


def test_aggregate_keeps_unmeasured_absent():
    pair = bc.CorpusPair(id="p", a="x", b="y", kind="same-genre")
    ok = bc.make_row(
        pair, "linear6", "ok", 1.0, family="crossfade", drift_ms=None, loudness_dip_lu=2.0
    )
    ok.update({"pass": False, "true_peak_dbtp": -3.0})
    bad = bc.make_row(pair, "linear6", "failed", 1.0)
    metrics = bc.aggregate([ok, bad], ("linear6", "auto"))
    assert "linear6_drift_ms" not in metrics  # never 0
    assert metrics["linear6_dip_lu"] == 2.0
    assert metrics["linear6_error_rate"] == 0.5
    assert metrics["linear6_pass_rate"] == 0.0
    assert not any(k.startswith("auto_") for k in metrics)


@pytest.fixture
def tiny_corpus(tmp_path, monkeypatch):
    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "cache"))
    audio = tmp_path / "audio"
    audio.mkdir()
    tracks, pairs = [], []
    for index, name in enumerate(("aa", "bb", "cc")):
        samples, _ = generate_track(bpm=120 + 4 * index, bars=24, seed=index)
        write_audio(audio / f"{name}.wav", samples)
        (audio / f"{name}.mp3").write_bytes((audio / f"{name}.wav").read_bytes())
        tracks.append(
            {
                "id": name,
                "title": name.upper(),
                "artist": "synthetic",
                "genre": "synthetic",
                "license": "CC0-1.0",
                "source_url": "https://example.test/" + name,
                "attribution": "synthetic",
            }
        )
    pairs.append({"id": "ab", "a": "aa", "b": "bb", "kind": "same-genre"})
    pairs.append({"id": "bc", "a": "bb", "b": "cc", "kind": "cross-genre"})
    pairs.append({"id": "ca", "a": "cc", "b": "zz_missing", "kind": "cross-genre"})
    tracks.append({**tracks[0], "id": "zz_missing"})
    return bc.Corpus.model_validate({"tracks": tracks, "pairs": pairs}), audio


def test_run_corpus_baselines_budget_and_listen_input(tiny_corpus, tmp_path):
    manifest, audio = tiny_corpus
    excerpts = tmp_path / "ex"
    result, rows = bc.run_corpus(
        manifest, audio, systems=bc.BASELINES, excerpts=excerpts, log=lambda _: None
    )
    assert len(rows) == 4  # two runnable pairs x two systems; the third has missing audio
    assert result.metrics["linear6_pairs"] == 2
    assert "linear6_drift_ms" not in result.metrics
    assert "linear6_low_overlap_bars" in result.metrics
    assert any("audio missing" in n for n in result.notes)
    path = bc.listen_input(manifest, rows, excerpts, bc.BASELINES)
    data = json.loads(path.read_text())
    assert len(data["pairs"]) == 2
    assert set(data["pairs"][0]["systems"]) == set(bc.BASELINES)
    rows_path = bc.write_rows(tmp_path / "rows.json", manifest, rows)
    assert json.loads(rows_path.read_text())["version"] == "corpus-rows/v1"
    out = tmp_path / "res"
    write_result(result, out)
    latest = (out / "LATEST.md").read_text()
    assert "| linear6 |" in latest
    assert "n/a" in latest
    assert load_results(out)[0].kind == "corpus"
    write_latest(out)
    stopped, none = bc.run_corpus(manifest, audio, systems=("linear6",), budget_minutes=0.0)
    assert none == []
    assert any("Not run" in n for n in stopped.notes)


def test_mixconsole_row_failure_and_success(tiny_corpus, tmp_path, monkeypatch):
    manifest, audio = tiny_corpus
    pair = manifest.pairs[0]
    import mixconsole.service as service

    def boom(*args: object, **kwargs: object):
        raise ValueError("no candidate passed verification")

    monkeypatch.setattr(service, "mix_pair", boom)
    row = bc.run_mixconsole(pair, "auto", audio / "aa.wav", audio / "bb.wav", 120, tmp_path, None)
    assert row["status"] == "failed"
    assert "no candidate" in str(row["reason"])


def test_mixconsole_row_success_with_stand_in_mix(tiny_corpus, tmp_path, monkeypatch):
    from types import SimpleNamespace

    import mixconsole.service as service
    from mixconsole.verify.metrics import SeamMetrics

    manifest, audio = tiny_corpus
    metric = SeamMetrics(None, 0.5, 0.0, -2.0, 0, None, True, "ok")

    def fake(a, b, *, out, report_dir, **kwargs):
        out.parent.mkdir(parents=True, exist_ok=True)
        (out.parent / "mix.wav").write_bytes((audio / "aa.wav").read_bytes())
        transition = SimpleNamespace(
            tempo=SimpleNamespace(tempo_map=[]),
            length_bars=4,
            beats_per_bar=4,
            exit=SimpleNamespace(seconds=5.0),
            family="beatmatch_blend",
        )
        return SimpleNamespace(
            mixscript=SimpleNamespace(transitions=[transition]),
            metrics=metric,
            chosen_id="c1",
            paths={"audio": out.parent / "mix.wav"},
        )

    monkeypatch.setattr(service, "mix_pair", fake)
    excerpts = tmp_path / "ex"
    row = bc.run_mixconsole(
        manifest.pairs[0], "auto", audio / "aa.wav", audio / "bb.wav", 120, tmp_path / "w", excerpts
    )
    assert row["status"] == "ok"
    assert row["drift_ms"] is None
    assert (excerpts / str(row["excerpt"])).is_file()


@pytest.mark.slow
def test_mixconsole_row_success_real(tiny_corpus, tmp_path):
    manifest, audio = tiny_corpus
    row = bc.run_mixconsole(
        manifest.pairs[0], "smooth", audio / "aa.wav", audio / "bb.wav", 120, tmp_path, None
    )
    assert row["status"] == "ok", row


def test_external_engine_absent(tiny_corpus, tmp_path):
    from mixconsole.bench.external import run_automix_engine

    manifest, audio = tiny_corpus
    row = run_automix_engine(manifest.pairs[0], audio / "aa.mp3", audio / "bb.mp3", tmp_path, None)
    assert row["status"] == "failed"
    assert "not set up" in str(row["reason"])


def test_cli_corpus(tiny_corpus, tmp_path, monkeypatch):
    manifest, audio = tiny_corpus
    pairs = tmp_path / "pairs.yaml"
    import yaml

    pairs.write_text(yaml.safe_dump(manifest.model_dump(mode="json")), encoding="utf-8")
    cache_audio = Path(tmp_path / "cache" / "corpus" / "audio")
    cache_audio.parent.mkdir(parents=True)
    audio.rename(cache_audio)
    out = tmp_path / "out"
    run = CliRunner().invoke(
        app,
        [
            "bench",
            "corpus",
            "--quick",
            "--systems",
            "linear6",
            "--pairs",
            str(pairs),
            "--out",
            str(out),
        ],
    )
    assert run.exit_code == 0, run.output
    assert (out / "LATEST.md").exists()
    assert list((out / "rows").glob("*.json"))
    assert "Listening input" in run.output
    bad = CliRunner().invoke(app, ["bench", "corpus", "--systems", "nope"])
    assert bad.exit_code != 0
