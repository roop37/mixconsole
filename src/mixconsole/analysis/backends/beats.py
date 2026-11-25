"""Onset/DP beat tracking with attack refinement and accent-based bar phase."""

import itertools
from importlib import import_module
from typing import Any

import numpy as np

from mixconsole.analysis.features import Features, FloatArray, ndimage, signal
from mixconsole.analysis.interfaces import BeatResult
from mixconsole.analysis.model_manager import checkpoint_path


def bar_phase(features: Features, beats: FloatArray, sample_rate: int) -> tuple[int, list[float]]:
    if len(beats) < 3:
        return 4, beats[::4].tolist()
    frames = np.clip(
        np.rint(beats * features.sr / features.hop).astype(int), 0, len(features.onset) - 1
    )
    low = (features.spectrum[1:30] ** 2).sum(axis=0)
    change = np.linalg.norm(
        np.diff(features.chroma, axis=1, prepend=features.chroma[:, :1]), axis=0
    )
    attack = np.array(
        [
            np.max(
                np.abs(
                    features.mono[
                        int(t * sample_rate) : min(
                            len(features.mono), int(t * sample_rate) + sample_rate // 12
                        )
                    ]
                ),
                initial=0,
            )
            for t in beats
        ]
    )
    accents = attack / max(float(attack.max()), 1e-12)
    for curve, weight in ((low, 0.4), (change, 0.2)):
        values = np.array([np.max(curve[max(0, f - 2) : f + 5], initial=0) for f in frames])
        accents += weight * values / max(float(values.max()), 1e-12)
    choices: list[tuple[float, int, int]] = []
    for meter in (4, 3):
        for phase in range(meter):
            mask = np.arange(len(beats)) % meter == phase
            score = float(accents[mask].mean() - accents[~mask].mean())
            choices.append((score, meter, phase))
    _, meter, phase = max(choices, key=lambda item: item[0])
    return meter, beats[phase::meter].tolist()


def _onset_acf(features: Features) -> FloatArray:
    """Unbiased, normalised autocorrelation of the detrended onset envelope."""
    env = features.onset - np.convolve(features.onset, np.ones(64) / 64, mode="same")
    env = np.maximum(env, 0)
    n = len(env)
    if n < 4 or float(env.max(initial=0)) <= 0:
        return np.zeros(max(n, 1), dtype=np.float64)
    ac = np.correlate(env, env, mode="full")[n - 1 :] / np.arange(n, 0, -1)
    return np.asarray(ac / max(float(ac[0]), 1e-12), dtype=np.float64)


def estimate_tempo(
    features: Features, low: float = 70.0, high: float = 180.0
) -> tuple[float, list[float]]:
    """Noise-robust global tempo: comb-filtered onset ACF, then metrical-level choice.

    Returns the chosen BPM and the other metrical candidates (half, double, 2/3, 3/2)
    inside the musical range, so callers can reason about octave ambiguity.
    """
    ac = _onset_acf(features)
    fps = features.sr / features.hop

    def acf(lag: float) -> float:
        i = int(lag)
        if i + 1 >= len(ac):
            return 0.0
        frac = lag - i
        return float((1 - frac) * ac[i] + frac * ac[i + 1])

    def comb(bpm: float) -> float:
        period = 60 / bpm * fps
        return sum(acf(k * period) for k in (1, 2, 3, 4)) / 4

    grid = np.arange(low / 2, high * 2, 0.05)
    best = float(grid[int(np.argmax([comb(b) for b in grid]))])
    ratios = (1 / 4, 1 / 3, 1 / 2, 2 / 3, 1, 3 / 2, 2, 3, 4)
    candidates = sorted({round(best * r, 3) for r in ratios if low <= best * r <= high})
    if not candidates:
        return float(np.clip(best, low, high)), []

    def pulse(bpm: float) -> float:
        period = 60 / bpm * fps
        return (acf(period) + acf(2 * period)) / 2

    def prior(bpm: float) -> float:
        return float(np.exp(-0.5 * np.log2(bpm / 120) ** 2))

    choice = max(candidates, key=lambda b: pulse(b) * prior(b))
    # Prefer the faster octave when its single-beat pulse is nearly as strong.
    if choice * 2 <= high and acf(60 / (choice * 2) * fps) >= 0.8 * acf(60 / choice * fps):
        choice *= 2
    return float(choice), [c for c in candidates if abs(c - choice) > 0.5]


def track_beats(features: Features, bpm: float, tightness: float = 400.0) -> FloatArray:
    """Dynamic-programming beat tracker locked to a known period (Ellis 2007 style).

    Implemented in-house so tempo locking is deterministic across library versions
    and robust to noisy onset envelopes. Returns beat times in seconds.
    """
    env = features.onset - np.convolve(features.onset, np.ones(64) / 64, mode="same")
    env = np.maximum(env, 0)
    env = env / max(float(env.std()), 1e-12)
    fps = features.sr / features.hop
    period = 60 / bpm * fps
    n = len(env)
    if n < 2 * period:
        return np.zeros(0, dtype=np.float64)
    lags = np.arange(int(np.floor(period / 2)), int(np.ceil(period * 2)) + 1)
    penalty = -tightness * np.log(lags / period) ** 2
    score = env.copy()
    back = np.full(n, -1, dtype=np.int64)
    for t in range(int(lags[0]), n):
        valid = lags <= t
        prev = t - lags[valid]
        candidates = score[prev] + penalty[valid]
        k = int(np.argmax(candidates))
        if candidates[k] > 0:
            score[t] = env[t] + candidates[k]
            back[t] = prev[k]
    # Start the backtrace from the best-scoring frame within the final period.
    tail = int(max(0, n - np.ceil(period)))
    t = tail + int(np.argmax(score[tail:]))
    frames: list[int] = []
    while t >= 0:
        frames.append(t)
        t = int(back[t])
    frames.reverse()
    beats = np.asarray(frames, dtype=np.float64)
    # Extend over leading/trailing regions the chain may not reach.
    while beats.size and beats[0] - period >= 0:
        beats = np.insert(beats, 0, beats[0] - period)
    return beats / fps


def fill_gaps(beats: FloatArray) -> FloatArray:
    """Continue the beat grid through internal beatless regions (breakdowns, pads).

    Gaps longer than 1.5 local periods are filled with evenly spaced beats; leading
    and trailing regions are left alone so silence is never given beats.
    """
    if len(beats) < 3:
        return beats
    period = float(np.median(np.diff(beats)))
    filled: list[float] = []
    for a, b in itertools.pairwise(beats):
        filled.append(float(a))
        count = round((b - a) / period)
        if (b - a) > 1.5 * period and count >= 2:
            filled.extend(float(a + k * (b - a) / count) for k in range(1, count))
    filled.append(float(beats[-1]))
    return np.asarray(filled, dtype=np.float64)


def transient_candidates(features: Features, sr: int) -> FloatArray:
    """5 ms attack envelope with sample-level refinement (also preserves time zero)."""
    y = features.mono
    block = max(1, round(sr * 0.005))
    derivative = np.abs(np.diff(y, prepend=0))
    padded = np.pad(derivative, (0, (-len(y)) % block))
    attack = padded.reshape(-1, block).max(axis=1)
    # Local prominence, not a global absolute-level threshold.
    baseline = ndimage.median_filter(attack, size=41)
    envelope = np.maximum(attack - baseline, 0)
    peaks, _ = signal.find_peaks(
        np.pad(envelope, (1, 1)),
        distance=round(0.25 * sr / block),
        prominence=max(float(envelope.max()) * 0.06, 1e-7),
    )
    peaks = peaks - 1
    refined: list[float] = []
    for peak in peaks:
        start = max(0, int(peak) * block - block)
        end = min(len(y), (int(peak) + 2) * block)
        if end > start:
            attack_sample = start + int(np.argmax(derivative[start:end]))
            if attack_sample > 0 and abs(y[attack_sample - 1]) > abs(y[attack_sample]):
                attack_sample -= 1
            refined.append(attack_sample / sr)
    return np.array(sorted(set(refined)), dtype=np.float64)


class LibrosaBeatBackend:
    name = "librosa"
    version = "2"

    def analyze(self, features: Features, sample_rate: int) -> BeatResult:
        if np.max(np.abs(features.mono), initial=0) < 1e-6:
            return BeatResult([], [], 4, 0)
        candidates = transient_candidates(features, sample_rate)
        intervals = np.diff(candidates)
        # The onset-ACF estimate is robust to noise; raw transient gaps are only
        # trusted when they agree with it (clean, sample-accurate material).
        bpm, _ = estimate_tempo(features)
        dp = track_beats(features, bpm)
        # A dense, locally continuous onset train supplies variable-tempo timing,
        # including edge beats that a spectral window/DP cannot observe.
        transient_bpm = 60 / float(np.median(intervals)) if len(intervals) else 0.0
        regular = (
            abs(transient_bpm - bpm) / bpm < 0.15
            and len(intervals) >= 3
            and np.mean((intervals >= 60 / 180 * 0.95) & (intervals <= 60 / 70 * 1.05)) > 0.9
        )
        continuous = len(intervals) >= 2 and float(np.median(abs(np.diff(intervals)))) < 0.08
        if regular and continuous:
            beats = candidates
        else:
            beats = dp
            if len(candidates):
                beats = np.array(
                    [
                        candidates[np.argmin(abs(candidates - t))]
                        if np.min(abs(candidates - t)) < 0.035
                        else t
                        for t in dp
                    ]
                )
        beats = np.unique(beats[(beats >= 0) & (beats < len(features.mono) / sample_rate)])
        beats = fill_gaps(beats)
        meter, downbeats = bar_phase(features, beats, sample_rate)
        intervals = np.diff(beats)
        confidence = (
            0.0
            if len(intervals) < 2
            else float(
                np.clip(
                    1 - np.median(abs(np.diff(intervals))) / max(float(np.median(intervals)), 1e-9),
                    0,
                    1,
                )
            )
        )
        # A regular bass note can form a stable grid without providing clear
        # percussive evidence. Report that ambiguity instead of high certainty.
        onset_median = float(np.median(features.onset))
        onset_contrast = float(np.quantile(features.onset, 0.99)) / max(onset_median, 1e-6)
        confidence *= float(np.clip((onset_contrast - 7) / 20, 0, 1))
        return BeatResult(beats.tolist(), downbeats, meter, confidence)


class BeatThisBackend:
    """Lazy CPU inference; a locally supplied, verified checkpoint avoids downloads."""

    name = "beat_this"
    version = "1"

    def analyze(self, features: Features, sample_rate: int) -> BeatResult:
        checkpoint = str(checkpoint_path())
        torch: Any = import_module("torch")
        inference: Any = import_module("beat_this.inference")
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(0)
            model = inference.Audio2Beats(checkpoint_path=checkpoint, device="cpu", dbn=False)
            raw_beats, raw_downbeats = model(features.mono.astype(np.float32), sample_rate)
        beats = np.unique(np.asarray(raw_beats, dtype=np.float64))
        beats = beats[(beats >= 0) & (beats < len(features.mono) / sample_rate)]
        downbeats = (
            sorted({float(beats[np.argmin(abs(beats - float(t)))]) for t in raw_downbeats})
            if len(beats)
            else []
        )
        meter, estimated = bar_phase(features, beats, sample_rate)
        return BeatResult(beats.tolist(), downbeats or estimated, meter, 0.8 if len(beats) else 0.0)
