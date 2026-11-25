"""Tempo continuity, bar energy and novelty-aligned musical phrases."""

from typing import Literal

import numpy as np

from mixconsole.analysis.backends.sections import novelty
from mixconsole.analysis.features import Features, FloatArray
from mixconsole.analysis.models import Bar, Phrase, Section, TempoSegment


def tempo_map(beats: list[float], duration: float) -> tuple[float | None, list[TempoSegment]]:
    """Global tempo and piecewise tempo segments from beat times.

    Steady tracks are detected by the residual of a least-squares beat-index fit, so
    frame-quantisation jitter neither splits them into spurious segments nor rounds
    the tempo. Varying tracks use 8-beat sliding least-squares local tempo.
    """
    if len(beats) < 2:
        return None, []
    times = np.asarray(beats, dtype=np.float64)
    index = np.arange(len(times), dtype=np.float64)
    fit = np.asarray(np.polyfit(index, times, 1), dtype=np.float64)
    slope, intercept = float(fit[0]), float(fit[1])
    residual = float(np.sqrt(np.mean((times - (slope * index + intercept)) ** 2)))
    if len(times) < 8 or residual < min(0.02, 0.1 * slope):
        global_bpm = float(60 / slope)
        return global_bpm, [TempoSegment(start=beats[0], end=duration, bpm=global_bpm)]
    half = 4
    local = np.empty(len(times) - 1)
    for i in range(len(times) - 1):
        lo, hi = max(0, i - half), min(len(times), i + half + 1)
        local[i] = 60 / float(np.polyfit(index[lo:hi], times[lo:hi], 1)[0])
    global_bpm = float(np.median(local))
    boundaries = [0]
    for i in range(4, len(local), 4):
        if abs(float(np.median(local[boundaries[-1] : i + 1])) - float(local[i])) >= 1:
            boundaries.append(i)
    segments: list[TempoSegment] = []
    for i, start in enumerate(boundaries):
        stop = boundaries[i + 1] if i + 1 < len(boundaries) else len(local)
        segments.append(
            TempoSegment(
                start=beats[start],
                end=beats[stop] if stop < len(local) else duration,
                bpm=float(np.median(local[start:stop])),
            )
        )
    return global_bpm, segments


def bars_and_energy(
    features: Features, downbeats: list[float], duration: float, sr: int
) -> tuple[list[Bar], FloatArray]:
    if not downbeats:
        return [], np.zeros((0, 5), dtype=np.float64)
    bars = [Bar(start=a, end=b) for a, b in zip(downbeats, [*downbeats[1:], duration], strict=True)]
    energy = np.zeros((len(bars), 5), dtype=np.float64)
    frequencies = np.linspace(0, features.sr / 2, features.spectrum.shape[0])
    band_curves = [
        (features.spectrum[(frequencies >= lo) & (frequencies < hi)] ** 2).mean(axis=0)
        for lo, hi in ((0, 150), (150, 2000), (2000, features.sr / 2 + 1))
    ]
    for i, bar in enumerate(bars):
        chunk = features.mono[round(bar.start * sr) : round(bar.end * sr)]
        left = min(len(features.onset) - 1, round(bar.start * features.sr / features.hop))
        right = max(left + 1, min(len(features.onset), round(bar.end * features.sr / features.hop)))
        energy[i] = [
            float(np.sqrt(np.mean(chunk**2))),
            float(features.onset[left:right].mean()),
            *[float(curve[left:right].mean()) for curve in band_curves],
        ]
    return bars, energy


def phrases(features: Features, bars: list[Bar], energy: FloatArray) -> list[Phrase]:
    if not bars:
        return []
    nov = novelty(features)
    frequencies = np.linspace(0, features.sr / 2, features.spectrum.shape[0])
    highs = (features.spectrum[frequencies > 2500] ** 2).mean(axis=0)
    values = np.zeros(len(bars))
    for i, bar in enumerate(bars):
        frame = round(bar.start * features.sr / features.hop)
        values[i] = float(highs[max(0, frame - 2) : frame + 12].max(initial=0))
    values /= max(float(values.max()), 1e-12)
    changes = abs(np.diff(energy[:, 0], prepend=energy[0, 0]))
    changes /= max(float(changes.max()), 1e-12)
    novelty_values = np.interp([b.start for b in bars], features.times, nov)
    novelty_values /= max(float(novelty_values.max()), 1e-12)
    values += 0.2 * changes + 0.2 * novelty_values
    choices: list[tuple[float, Literal[4, 8, 16], int]] = []
    lengths: tuple[Literal[4, 8, 16], ...] = (8, 4, 16)
    for length in lengths:
        for offset in range(min(length, len(bars))):
            mask = np.arange(len(bars)) % length == offset
            # Penalize missing novelty events and reward precision and coverage.
            precision = float(values[mask].mean())
            coverage = float(values[mask].sum() / max(float(values.sum()), 1e-12))
            score = 2 * precision * coverage / max(precision + coverage, 1e-12)
            choices.append((score, length, offset))
    score, length, offset = max(choices, key=lambda c: c[0])
    return [
        Phrase(start=bars[i].start, start_bar=i, length_bars=length, confidence=min(1.0, score))
        for i in range(offset, len(bars), length)
    ]


def bar_sections(
    features: Features,
    bars: list[Bar],
    energy: FloatArray,
    duration: float,
    fallback: list[Section],
    *,
    grid: int = 4,
    novelty_threshold: float = 0.2,
    dynamics_threshold_db: float = 4.5,
) -> list[Section]:
    """Section boundaries on the bar grid, from harmonic/timbral novelty or energy change.

    DJ-relevant sections start on phrase-grid bars, so candidates are restricted to
    every ``grid`` bars. A candidate is a boundary when timbral novelty exceeds an
    absolute and track-relative thresholds, or band/RMS energy changes by ``dynamics_threshold_db``
    between the ``grid`` bars before and after (robust to broadband noise). Without a
    bar grid the backend's frame-level sections are returned unchanged.
    """
    if len(bars) < 2 * grid:
        return fallback
    curve = novelty(features)
    # Transient accents can exceed a fixed threshold after compression even when
    # the arrangement is unchanged. Require a peak above the track's usual novelty.
    peak_threshold = max(novelty_threshold, 1.5 * float(np.quantile(curve, 0.95)))
    fps = features.sr / features.hop
    # -40 dB floor relative to the track keeps digital silence from exploding ratios.
    floor = 1e-4 * np.maximum(energy.mean(axis=0), 1e-12)
    # Bands carrying < 5 % of the track's band energy (e.g. sparse cymbals) are ignored.
    means = energy[:, 2:].mean(axis=0)
    active = means >= 0.05 * max(float(means.sum()), 1e-12)
    scores: dict[int, float] = {}
    for b in range(grid, len(bars) - grid // 2, grid):
        start = bars[b].start
        half = (bars[b].end - bars[b].start) / 2
        lo = max(0, int((start - half) * fps))
        hi = min(len(curve), int((start + half) * fps) + 1)
        nov = float(curve[lo:hi].max(initial=0)) / peak_threshold
        before = energy[max(0, b - grid) : b]
        after = energy[b : min(len(bars), b + grid)]
        rms_db = 20 * abs(
            np.log10((after[:, 0].mean() + floor[0]) / (before[:, 0].mean() + floor[0]))
        )
        band_db = 10 * np.abs(
            np.log10(
                (after[:, 2:].mean(axis=0) + floor[2:]) / (before[:, 2:].mean(axis=0) + floor[2:])
            )
        )
        band_change = float(band_db[active].max(initial=0))
        dyn = max(float(rms_db), band_change) / dynamics_threshold_db
        scores[b] = max(nov, dyn)
    boundaries = [
        b
        for b, score in scores.items()
        if score >= 1 and score >= scores.get(b - grid, 0) and score >= scores.get(b + grid, 0)
    ]
    starts = [0.0] + [bars[b].start for b in boundaries]
    source = (fallback[0].source if fallback else "novelty") + "+bars"
    return [
        Section(start=a, end=e, source=source)
        for a, e in zip(starts, [*starts[1:], duration], strict=True)
    ]
