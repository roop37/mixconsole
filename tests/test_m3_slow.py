"""Slow M3 tests that run the real htdemucs weights on synthetic audio (CPU or MPS)."""

import json
from pathlib import Path

import numpy as np
import pytest

from mixconsole.analysis import analyze, model_manager
from mixconsole.analysis.backends import stems as stem_backend
from mixconsole.io import write_audio
from mixconsole.service import mix_pair
from mixconsole.testing.synth import generate_track

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def weights() -> None:
    pytest.importorskip("demucs")
    try:
        model_manager.fetch_htdemucs()
    except (OSError, ValueError) as exc:  # offline or blocked
        pytest.skip(f"htdemucs weights unavailable: {exc}")


def test_real_htdemucs_null_test_and_vocal_bars(
    weights: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(stem_backend, "_separator", None)
    audio, _ = generate_track(bpm=120, bars=16, vocal_bars=(4, 5, 6, 10), seed=1)
    path = write_audio(tmp_path / "t.wav", audio)
    result = analyze(path, backends={"vocals": "stems"}, cache_dir=tmp_path / "cache")
    assert result.stems is not None
    assert result.vocal_activity is not None
    assert result.vocal_activity.source == "stem"
    voiced = {i for i, f in enumerate(result.vocal_activity.per_bar) if f > 0.2}
    # A synthetic buzz is not a real voice: the model may miss bars, but must not invent any.
    assert voiced <= {4, 5, 6, 10}
    assert len(voiced) >= 2
    window = stem_backend.window_frames("exit", result.duration, 0, result.edges.silence_tail)
    stems = stem_backend.separate_window(
        audio, result.pcm_sha256, window, cache_root=tmp_path / "cache"
    )
    original = audio[window[0] : window[1]]
    error = float(np.sqrt(np.mean((stem_backend.resum(stems.stems) - original) ** 2)))
    assert 20 * np.log10(error / float(np.sqrt(np.mean(original**2))) + 1e-12) < -60
    assert stems.stats["device"] in ("cpu", "mps", "cuda")


def test_real_htdemucs_mix_pair_has_no_vocal_or_bass_overlap(
    weights: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(stem_backend, "_separator", None)
    monkeypatch.setenv("MIXCONSOLE_STEMS", "on")
    monkeypatch.setenv("MIXCONSOLE_WORKERS", "1")
    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "cache"))
    a, _ = generate_track(bpm=124, bars=24, vocal_bars=tuple(range(12, 18)), seed=3)
    b, _ = generate_track(bpm=124, bars=24, vocal_bars=(*tuple(range(4)), 14, 15), seed=4)
    write_audio(tmp_path / "a.wav", a)
    write_audio(tmp_path / "b.wav", b)
    result = mix_pair(tmp_path / "a.wav", tmp_path / "b.wav", out=tmp_path / "m.wav", candidates=3)
    assert result.metrics is not None
    assert result.metrics.passed
    report = json.loads(result.paths["report_json"].read_text())
    stem_checks = [c for c in report["verification"] if c.get("vocal_overlap_seconds") is not None]
    for check in stem_checks:
        assert check["bass_overlap_bars"] is not None
    if result.metrics.vocal_overlap_seconds is not None:
        assert result.metrics.vocal_overlap_seconds <= 60 / 124
        assert result.metrics.bass_overlap_bars == 0.0
