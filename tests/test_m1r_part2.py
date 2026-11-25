"""M1R degradation and optional-data integrity checks."""

import io
import shutil

import numpy as np
import pytest

from mixconsole.analysis import analyze
from mixconsole.analysis.model_manager import checkpoint_path, fetch_beat_this
from mixconsole.bench import cc_sanity
from mixconsole.bench.accuracy import add_pink_noise, mp3_round_trip, run_accuracy
from mixconsole.bench.metrics import beat_f_measure, tempo_acc2
from mixconsole.io import write_audio
from mixconsole.testing.synth import generate_track


def test_humanised_sparse_and_breakdown_fixture():
    audio, truth = generate_track(
        bpm=128,
        bars=32,
        percussion="sparse",
        timing_jitter_ms=10,
        breakdown_bars=tuple(range(16, 24)),
        seed=17,
    )
    assert audio.shape[0] == round(truth["duration"] * 44100)
    assert len(truth["beat_times"]) == 128
    assert truth["downbeats"][16] == pytest.approx(30, abs=1 / 44100)
    assert any(abs(b - (i * 60 / 128)) > 0.001 for i, b in enumerate(truth["beat_times"]))
    with pytest.raises(ValueError, match="timing_jitter"):
        generate_track(timing_jitter_ms=11)


def test_pink_noise_snr_and_seed():
    audio, _ = generate_track(bars=4)
    noisy = add_pink_noise(audio, 20, 7)
    assert np.array_equal(noisy, add_pink_noise(audio, 20, 7))
    noise = noisy - audio
    snr = 20 * np.log10(np.sqrt(np.mean(audio**2)) / np.sqrt(np.mean(noise**2)))
    assert snr == pytest.approx(20, abs=0.01)


@pytest.mark.parametrize(
    "condition", ["pink20", "compression", "humanized", "sparse", "none", "mp3"]
)
def test_degraded_track_analysis(condition, tmp_path):
    if condition == "mp3" and shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg unavailable")
    audio, truth = generate_track(
        bpm=128,
        bars=16,
        seed=128,
        percussion="sparse" if condition == "sparse" else "none" if condition == "none" else "both",
        timing_jitter_ms=10 if condition == "humanized" else 0,
    )
    if condition == "pink20":
        audio = add_pink_noise(audio, 20, 128)
    elif condition == "compression":
        audio = np.tanh(4 * audio).astype(np.float32)
    elif condition == "mp3":
        audio = mp3_round_trip(audio, tmp_path)
    result = analyze(write_audio(tmp_path / "degraded.wav", audio), use_cache=False)
    assert tempo_acc2(result.global_bpm, 128)
    assert beat_f_measure(result.beats, truth["beat_times"]) >= 0.8
    assert len(result.sections) == 1
    if condition == "none":
        assert result.beat_confidence < 0.2


@pytest.mark.slow
def test_quick_accuracy_benchmark_targets():
    result = run_accuracy(quick=True)
    metrics = result.metrics
    assert metrics["tempo_acc1_snr20"] >= 0.9
    assert metrics["tempo_acc2_snr20"] >= 0.98
    assert metrics["beat_f_mean_snr20"] >= 0.9
    assert metrics["tempo_acc1_pink20"] >= 0.9
    assert metrics["sections_homogeneous_single_rate_snr20"] == 1
    assert metrics["sections_inserted_breakdown_within_bar"] == 1
    assert metrics["beat_confidence_mean_no_percussion"] < 0.2
    if shutil.which("ffmpeg") is not None:
        assert metrics["tempo_acc2_mp3"] == 1


def test_accuracy_benchmark_smoke(tmp_path):
    audio, truth = generate_track(bpm=124, bars=4, seed=3)
    result = analyze(write_audio(tmp_path / "accuracy-smoke.wav", audio), use_cache=False)
    assert tempo_acc2(result.global_bpm, 124)
    assert beat_f_measure(result.beats, truth["beat_times"]) >= 0.9


def test_cc_manifest_and_cached_analysis(monkeypatch, tmp_path):
    entries = cc_sanity.tracks()
    assert 10 <= len(entries) <= 15
    assert {"Indian / Bollywood house", "hip-hop vocal", "punk rock"} <= {
        track.genre for track in entries
    }
    track = entries[0]
    monkeypatch.setattr(cc_sanity, "tracks", lambda: [track])
    monkeypatch.setattr(cc_sanity, "cache_root", lambda: tmp_path)
    directory = tmp_path / "datasets" / "cc_sanity"
    directory.mkdir(parents=True)
    audio, _ = generate_track(bars=4, bpm=120)
    wav = write_audio(directory / "synthetic.wav", audio)
    (directory / f"{track.id}.mp3").write_bytes(wav.read_bytes())
    result = cc_sanity.run_cc_sanity()
    assert result.metrics["evaluated"] == 1
    assert "reference unknown" in result.notes[1]
    (directory / f"{track.id}.mp3").unlink()
    with pytest.raises(ValueError, match="--fetch"):
        cc_sanity.run_cc_sanity()


def test_cc_fetch_license_check_and_model_hash(monkeypatch, tmp_path):
    track = cc_sanity.tracks()[0]
    page = b"CC0 1.0 Universal License https:\\/\\/files.freemusicarchive.org\\/track.mp3"
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, timeout))
        return io.BytesIO(page if len(calls) == 1 else b"audio" * 300)

    monkeypatch.setattr(cc_sanity, "urlopen", fake_urlopen)
    path = cc_sanity.fetch_track(track, tmp_path)
    assert path.stat().st_size == 1500
    assert len(calls) == 2
    assert cc_sanity.fetch_track(track, tmp_path) == path
    path.unlink()
    monkeypatch.setattr(cc_sanity, "urlopen", lambda *_args, **_kwargs: io.BytesIO(b"wrong"))
    with pytest.raises(ValueError, match="license changed"):
        cc_sanity.fetch_track(track, tmp_path)

    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path))
    assert checkpoint_path() == tmp_path / "models" / "beat_this" / "final0.ckpt"
    model = checkpoint_path()
    model.parent.mkdir(parents=True)
    model.write_bytes(b"bad")
    with pytest.raises(ValueError, match="hash mismatch"):
        fetch_beat_this()


def test_cc_fetch_failure_keeps_other_track_results(monkeypatch, tmp_path):
    first, second = cc_sanity.tracks()[:2]
    monkeypatch.setattr(cc_sanity, "tracks", lambda: [first, second])
    monkeypatch.setattr(cc_sanity, "cache_root", lambda: tmp_path)
    directory = tmp_path / "datasets" / "cc_sanity"
    directory.mkdir(parents=True)
    audio, _ = generate_track(bars=4)
    wav = write_audio(directory / "synthetic.wav", audio)
    (directory / f"{first.id}.mp3").write_bytes(wav.read_bytes())

    def unavailable(track, path):
        if track.id == second.id:
            raise OSError("HTTP 403")
        return path / f"{track.id}.mp3"

    monkeypatch.setattr(cc_sanity, "fetch_track", unavailable)
    result = cc_sanity.run_cc_sanity(fetch=True)
    assert result.metrics["evaluated"] == 1
    assert result.metrics["missing"] == 1
    assert f"Fetch failed {second.id}: HTTP 403" in result.notes
