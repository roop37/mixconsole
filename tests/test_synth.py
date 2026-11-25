"""Verify synthesis against independently calculated musical ground truth."""

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mixconsole.testing.synth import generate_track
from tests.synth import generate_track as fixture_generate_track

RATE = 44100


def test_public_and_test_imports_match():
    assert fixture_generate_track is generate_track


def test_beat_phrase_silence_and_accents():
    audio, truth = generate_track(
        bpm=120,
        bars=9,
        percussion="click",
        bass=False,
        pad=False,
        silence_head=0.25,
        silence_tail=0.5,
    )
    assert audio.dtype == np.float32
    assert audio.shape == (round(18.75 * RATE), 2)
    np.testing.assert_allclose(truth["beat_times"], np.arange(36) * 0.5 + 0.25)
    np.testing.assert_allclose(truth["downbeats"], np.arange(9) * 2 + 0.25)
    assert truth["phrase_starts"] == [0.25, 16.25]
    assert not audio[: round(0.25 * RATE)].any()
    assert not audio[round(18.25 * RATE) :].any()
    # Each click starts on the exact annotated sample; downbeats are accented.
    frames = np.rint(np.array(truth["beat_times"]) * RATE).astype(int)
    expected = np.where(np.arange(36) % 4 == 0, 0.24, 0.132)
    np.testing.assert_allclose(audio[frames, 0], expected, atol=1e-7)


@pytest.mark.parametrize("end_bpm", [80, 180])
def test_ramp_integrates_tempo(end_bpm):
    _, truth = generate_track(
        bpm=120, end_bpm=end_bpm, bars=3, bass=False, pad=False, silence_head=0.1
    )
    times = np.array([*truth["beat_times"], truth["music_end"]]) - 0.1
    slope = (end_bpm - 120) / 12
    recovered_beats = 120 * np.expm1(slope * times / 60) / slope
    np.testing.assert_allclose(recovered_beats, np.arange(13), atol=4e-5)
    diffs = np.diff(times)
    assert np.all(np.diff(diffs) < 0) if end_bpm > 120 else np.all(np.diff(diffs) > 0)


@pytest.mark.parametrize("signature", [(3, 4), (6, 8), (7, 8)])
def test_time_signature(signature):
    _, truth = generate_track(bpm=120, bars=2, time_signature=signature, phrase_bars=1)
    numerator, denominator = signature
    pulse_seconds = 0.5 * 4 / denominator
    assert len(truth["beat_times"]) == 2 * numerator
    assert truth["downbeats"] == truth["phrase_starts"]
    assert truth["music_end"] == pytest.approx(2 * numerator * pulse_seconds, abs=1 / RATE)


def test_vocals_only_in_annotated_regions():
    audio, truth = generate_track(
        bpm=120,
        bars=3,
        percussion="none",
        bass=False,
        pad=False,
        vocal_bars=(2, 0, 2),
        silence_head=0.25,
    )
    assert truth["vocal_regions"] == [(0.75, 1.75), (4.75, 5.75)]
    mask = np.zeros(len(audio), dtype=bool)
    for start, stop in truth["vocal_regions"]:
        left, right = round(start * RATE), round(stop * RATE)
        mask[left:right] = True
        assert np.max(np.abs(audio[left:right])) > 0.01
    assert not audio[~mask].any()


def test_key_root_and_pad_chord_spectrum():
    bass, truth = generate_track(bpm=60, bars=1, key="A minor", percussion="none", pad=False)
    frequencies = np.fft.rfftfreq(len(bass), 1 / RATE)
    spectrum = np.abs(np.fft.rfft(bass[:, 0]))
    assert frequencies[np.argmax(spectrum)] == pytest.approx(110, abs=0.5)
    assert truth["key"] == "A minor"
    pad, _ = generate_track(bpm=60, bars=1, key="A minor", percussion="none", bass=False)
    spectrum = np.abs(np.fft.rfft(pad[:, 0]))
    for expected in [440, 440 * 2 ** (3 / 12), 440 * 2 ** (7 / 12)]:
        nearby = np.abs(frequencies - expected) < 0.5
        assert spectrum[nearby].max() > spectrum.max() * 0.6


def test_seeded_repeatability_and_stereo():
    args = {"bars": 2, "vocal_bars": (1,), "seed": 23}
    audio, truth = generate_track(**args)
    repeated, repeated_truth = generate_track(**args)
    assert audio.tobytes() == repeated.tobytes()
    assert truth == repeated_truth
    assert not np.array_equal(audio[:, 0], audio[:, 1])
    different, _ = generate_track(bars=2, vocal_bars=(1,), seed=24)
    assert not np.array_equal(audio, different)
    assert np.isfinite(audio).all()
    assert np.max(np.abs(audio)) < 1


@settings(max_examples=12, derandomize=True, deadline=None)
@given(bpm=st.floats(min_value=70, max_value=200, allow_nan=False), bars=st.integers(1, 3))
def test_constant_tempo_grid(bpm, bars):
    audio, truth = generate_track(bpm=bpm, bars=bars, percussion="click", bass=False, pad=False)
    expected = np.arange(bars * 4) * 60 / bpm
    np.testing.assert_allclose(truth["beat_times"], expected, atol=0.5 / RATE)
    assert len(audio) == round(bars * 4 * 60 / bpm * RATE)
    assert math.isclose(truth["duration"], len(audio) / RATE)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"bpm": 0},
        {"bpm": float("nan")},
        {"end_bpm": -1},
        {"bars": 0},
        {"phrase_bars": 0},
        {"time_signature": (4, 3)},
        {"key": "H major"},
        {"vocal_bars": (8,)},
        {"silence_head": -0.1},
        {"seed": -1},
    ],
)
def test_invalid_synthesis_arguments(kwargs):
    with pytest.raises(
        ValueError,
        match=r"positive|finite|key|signature|range|invalid|bars|BPM|seed|silence|sample|vocal",
    ):
        generate_track(**kwargs)
