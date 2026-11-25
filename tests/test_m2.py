"""Fast M2 contract, DSP, and synthetic pair acceptance checks."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from mixconsole.analysis import analyze
from mixconsole.config import Settings
from mixconsole.io import SAMPLE_RATE, load_audio, write_audio
from mixconsole.mixscript import dumps_mixscript, load_mixscript
from mixconsole.plan.candidates import plan_pair, tempo_choice
from mixconsole.plan.constraints import rejection_reason
from mixconsole.render.delay import echo
from mixconsole.render.eq import bands
from mixconsole.render.filters import sweep
from mixconsole.render.gain import curve
from mixconsole.render.graph import render_transition
from mixconsole.render.limiter import limit, true_peak_dbtp
from mixconsole.render.stretch import ramp_back, stretch
from mixconsole.score.heuristic import total, weights
from mixconsole.service import mix_pair
from mixconsole.service import plan_pair as service_plan
from mixconsole.testing.synth import generate_track
from mixconsole.verify import verify_seam


def _pair(root: Path, bpm_a: float = 120, bpm_b: float = 120) -> tuple[Path, Path]:
    paths = root / "a.wav", root / "b.wav"
    for path, bpm in zip(paths, (bpm_a, bpm_b), strict=True):
        audio, _ = generate_track(bpm=bpm, bars=8, seed=4)
        write_audio(path, audio)
    return paths


def test_mix_round_trip_and_three_previews(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "cache"))
    a, b = _pair(tmp_path)
    result = mix_pair(a, b, out=tmp_path / "mix.wav", report_dir=tmp_path / "report")
    script = load_mixscript(result.paths["mixscript"])
    assert script.version == "mixscript/v1.1"
    assert script.transitions[0].explanation is not None
    assert len(script.transitions[0].candidates) == 3
    assert all(c.preview_artifact for c in script.transitions[0].candidates)
    assert all(
        (tmp_path / "report" / str(c.preview_artifact)).exists()
        for c in script.transitions[0].candidates
    )
    assert all(r.reason for r in script.transitions[0].explanation.rejected_candidates)
    assert "<audio" in result.paths["report_html"].read_text()
    assert "https://" not in result.paths["report_html"].read_text()
    assert json.loads(result.paths["report_json"].read_text())["chosen_id"] == result.chosen_id
    assert dumps_mixscript(script) == result.paths["mixscript"].read_text()
    replay = render_transition(load_audio(a).samples, load_audio(b).samples, script)
    write_audio(tmp_path / "replay.wav", replay)

    def digest(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    assert digest(tmp_path / "mix.wav") == digest(tmp_path / "replay.wav")
    assert result.metrics is not None
    assert result.metrics.true_peak_dbtp <= -1


def test_plan_locks_and_no_sync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "cache"))
    a, b = _pair(tmp_path, 100, 140)
    analysis_a = analyze(a, cache_dir=tmp_path / "cache")
    analysis_b = analyze(b, cache_dir=tmp_path / "cache")
    assert tempo_choice(analysis_a, analysis_b, Settings())[1] == "no_sync"
    planned = plan_pair(analysis_a, analysis_b, Settings())
    assert planned.candidates
    assert all(c.family != "beatmatch_blend" for c in planned.candidates)
    assert all(r.reason for r in planned.rejected)
    locked = service_plan(a, b, locks={"exit": planned.candidates[0].exit_seconds})
    assert locked.mixscript.transitions[0].exit.seconds == planned.candidates[0].exit_seconds
    candidate = planned.candidates[0]
    assert (
        rejection_reason(analysis_a, analysis_b, candidate, Settings(), {"family": "gapless"})
        == "locked family"
    )
    assert total(candidate.features, "auto") == pytest.approx(candidate.score)
    assert sum(weights()["auto"].values()) == pytest.approx(1)


def test_dsp_curve_eq_stretch_filters_and_echo() -> None:
    n = SAMPLE_RATE // 2
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    source = np.column_stack(
        (0.1 * np.sin(2 * np.pi * 220 * t), 0.1 * np.sin(2 * np.pi * 440 * t))
    ).astype(np.float32)
    for kind in ("linear", "equal_power", "exponential", "step"):
        fade = curve(n, kind)
        assert fade[0] == pytest.approx(1)
        assert fade[-1] <= 0.001
    low, mid, high = bands(source)
    assert np.max(np.abs(low + mid + high - source)) < 1e-6
    assert np.isfinite(sweep(source[:2000], 40, 8000, "highpass")).all()
    assert np.isfinite(sweep(source[:2000], 200, 12000, "lowpass")).all()
    stretched = stretch(source, round(n * 1.04))
    assert len(stretched) == round(n * 1.04)
    assert np.isfinite(stretched).all()
    ramp, consumed = ramp_back(source, 100, 103, 1)
    assert consumed > 0
    assert len(ramp) > 0
    assert len(echo(source[:1000], 120)) > 1000
    limited = limit(source * 20)
    assert true_peak_dbtp(limited) <= -1
    metric = verify_seam(limited, 1000, 1000, bpm=120)
    assert metric.true_peak_dbtp <= -1
    assert metric.as_dict()["reason"]


def test_beat_warp_and_audio_derived_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from mixconsole.render.graph import RenderInspection
    from mixconsole.service import _candidate_script

    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "cache"))
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    left, _ = generate_track(bpm=100, bars=24, percussion="click", bass=False, pad=False)
    right, _ = generate_track(bpm=93, bars=24, percussion="click", bass=False, pad=False)
    write_audio(a, left)
    write_audio(b, right)
    analyses = [analyze(a, cache_dir=tmp_path / "cache"), analyze(b, cache_dir=tmp_path / "cache")]
    planned = plan_pair(*analyses, Settings())
    candidate = next(c for c in planned.candidates if c.family == "beatmatch_blend")
    script = _candidate_script(candidate, analyses, alternatives=[candidate], rejected=[])
    assert script.transitions[0].extensions["render.beat_warp"]
    assert script.transitions[0].automation
    assert any(e.name == "bass_swap" for e in script.transitions[0].effects)
    inspection = RenderInspection()
    rendered = render_transition(left, right, script, inspection=inspection)
    metric = verify_seam(
        rendered,
        round(candidate.exit_seconds * SAMPLE_RATE),
        round(candidate.duration * SAMPLE_RATE),
        bpm=candidate.bpm or 100,
        inspection=inspection,
    )
    assert metric.drift_ms < 5
    assert metric.low_overlap_bars <= 1
    assert np.isfinite(rendered).all()
    assert true_peak_dbtp(rendered) <= -1
    replay = render_transition(left, right, load_mixscript(_save_script(tmp_path, script)))
    assert np.array_equal(rendered, replay)


def _save_script(root: Path, script: object) -> Path:
    from mixconsole.mixscript.models import MixScript

    assert isinstance(script, MixScript)
    path = root / "plan.mixscript.json"
    path.write_text(dumps_mixscript(script), encoding="utf-8")
    return path


def test_stretcher_pitch_and_correlated_crossfade(tmp_path: Path) -> None:
    n = SAMPLE_RATE
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    tone = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    stereo = np.column_stack((tone, tone))
    stretched = stretch(stereo, round(1.07 * n))
    spectrum = np.abs(np.fft.rfft(stretched[:, 0], n=len(stretched) * 16))
    peak_bin = int(np.argmax(spectrum))
    frequency = peak_bin * SAMPLE_RATE / (len(stretched) * 16)
    cents = 1200 * np.log2(frequency / 440)
    assert abs(cents) < 5
    assert abs(len(stretched) / len(stereo) - 1.07) < 0.001
    fade_a = curve(n, "linear")
    fade_b = curve(n, "linear", incoming=True)
    assert np.max(np.abs(fade_a + fade_b - 1)) < 1e-5


def test_family_plugin_contract_and_rejection_reasons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mixconsole.plan.families import families, register

    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "cache"))
    a, b = _pair(tmp_path)
    left = analyze(a, cache_dir=tmp_path / "cache")
    right = analyze(b, cache_dir=tmp_path / "cache")
    planned = plan_pair(left, right, Settings())
    assert len(planned.candidates) <= Settings().max_candidates
    assert all(0 <= v <= 1 for c in planned.candidates for v in c.features.values())
    assert all(c.score <= 1 for c in planned.candidates)
    for family in families():
        assert family.name
        assert family.version
        same = [c for c in planned.candidates if c.family == family.name]
        if same:
            lanes, effects = family.automation(same[0])
            assert isinstance(lanes, list)
            assert isinstance(effects, list)
    with pytest.raises(ValueError, match="duplicate"):
        register(families()[0])
    c = planned.candidates[0]
    assert rejection_reason(left, right, c, Settings(), {"entry": -1}) == "locked entry cue"
    assert (
        rejection_reason(left, right, c, Settings(), {"length_bars": 100})
        == "locked transition length"
    )


def test_transition_benchmark_result_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from mixconsole.bench import transitions
    from mixconsole.verify.metrics import SeamMetrics

    def fake_mix(*_args: object, **_kwargs: object) -> SimpleNamespace:
        metric = SeamMetrics(0.0, 0.2, 0.0, -2.0, 0, 0.0, True, "passed")
        script = SimpleNamespace(transitions=[SimpleNamespace(family="trim_crossfade")])
        return SimpleNamespace(mixscript=script, metrics=metric)

    monkeypatch.setattr(transitions, "mix_pair", fake_mix)
    result = transitions.run_transitions(quick=True)
    assert result.kind == "transitions"
    assert result.metrics["trim_crossfade_pass_rate"] == 1.0
    assert "baseline_6s_linear_dip_lu" in result.metrics
    assert len(result.notes) == 2
