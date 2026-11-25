"""M1R regression suite: tempo, beat grid and sections under broadband noise.

Found in review (2026-11-18): the M1 tracker read 97 BPM as ~195 BPM at 10 dB SNR and
over-segmented homogeneous tracks. SNR is measured against the track's RMS.
"""

import numpy as np
import pytest

from mixconsole import analyze
from mixconsole.io import write_audio
from mixconsole.testing.synth import generate_track

from .test_analysis import f_measure

BAR_128 = 60 / 128 * 4


def noisy(audio: np.ndarray, snr_db: float | None, seed: int = 0) -> np.ndarray:
    if snr_db is None:
        return audio
    rms = float(np.sqrt(np.mean(audio**2)))
    noise = np.random.default_rng(seed).normal(0, rms / 10 ** (snr_db / 20), audio.shape)
    return (audio + noise).astype(audio.dtype)


def run(tmp_path, audio, name="track.wav"):
    return analyze(write_audio(tmp_path / name, audio), use_cache=False)


@pytest.mark.parametrize("snr", [20, 10])
@pytest.mark.parametrize("bpm", [90, 97, 124, 140, 174])
def test_tempo_and_grid_under_noise(tmp_path, bpm, snr):
    audio, truth = generate_track(bpm=bpm, bars=24, key="F# minor", seed=3)
    result = run(tmp_path, noisy(audio, snr))
    assert result.global_bpm is not None
    assert abs(result.global_bpm - bpm) <= 0.5
    assert f_measure(result.beats, truth["beat_times"]) >= 0.9
    # Known limit: bar phase at 10 dB SNR is not yet reliable (tracked in M1R evidence).
    if snr >= 20:
        assert f_measure(result.downbeats, truth["downbeats"]) >= 0.85


def test_three_four_under_noise(tmp_path):
    audio, truth = generate_track(bpm=110, bars=24, time_signature=(3, 4), seed=5)
    result = run(tmp_path, noisy(audio, 20, seed=1))
    assert result.meter == 3
    assert result.global_bpm is not None
    assert abs(result.global_bpm - 110) <= 0.5
    assert f_measure(result.downbeats, truth["downbeats"]) >= 0.9


@pytest.mark.parametrize("snr", [None, 30, 10])
def test_homogeneous_track_is_one_section(tmp_path, snr):
    audio, _ = generate_track(bpm=128, bars=32, key="F# minor", seed=3)
    assert len(run(tmp_path, noisy(audio, snr)).sections) == 1


def test_compressed_homogeneous_noisy_track_is_one_section(tmp_path):
    audio, _ = generate_track(bpm=128, bars=32, key="F# minor", seed=3)
    compressed = np.tanh(audio * 4).astype(np.float32)
    assert len(run(tmp_path, noisy(compressed, 10)).sections) == 1


@pytest.mark.parametrize("snr", [None, 20])
def test_breakdown_and_key_change_boundaries(tmp_path, snr):
    drums, _ = generate_track(bpm=128, bars=16, key="C major", seed=3)
    pads, _ = generate_track(bpm=128, bars=8, key="C major", percussion="none", seed=4)
    result = run(tmp_path, noisy(np.concatenate((drums, pads, drums)), snr), "breakdown.wav")
    starts = [round(s.start / BAR_128) for s in result.sections]
    assert starts == [0, 16, 24]
    # The beat grid continues through the beatless breakdown.
    assert len(result.bars) == 40

    other, _ = generate_track(bpm=128, bars=16, key="F# minor", seed=4)
    result = run(tmp_path, noisy(np.concatenate((drums, other)), snr), "keychange.wav")
    assert [round(s.start / BAR_128) for s in result.sections] == [0, 16]
