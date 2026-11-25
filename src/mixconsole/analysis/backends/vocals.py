"""Vocal activity per bar/beat plus lyric gaps (>= 300 ms).

Two backends share one 10 ms mask representation:

* ``heuristic``: a low-confidence spectral estimate (sustained 1-3.5 kHz energy share) over
  the whole track. It cannot tell a lead vocal from a lead synth, so it is never trusted for
  hard constraints.
* ``stems``: Demucs vocal stem RMS + spectral flatness (voicing) on the exit and entry
  windows (the only windows that are separated), overriding the heuristic there.
"""

from dataclasses import dataclass
from importlib import import_module
from typing import Any

import numpy as np
from numpy.typing import NDArray

from mixconsole.analysis.backends import stems as stem_backend
from mixconsole.analysis.interfaces import VocalContext, VocalResult
from mixconsole.analysis.model_manager import HTDEMUCS_SHA256
from mixconsole.analysis.models import (
    Span,
    StemsInfo,
    StemWindow,
    VocalActivity,
)
from mixconsole.io import SAMPLE_RATE

FRAME = 0.01  # seconds per mask frame
MIN_GAP = 0.3
HEURISTIC_CONFIDENCE = 0.3
STEM_CONFIDENCE = 0.9
BoolArray = NDArray[np.bool_]
FloatArray = NDArray[np.float64]
librosa: Any = import_module("librosa")
ndimage: Any = import_module("scipy.ndimage")


def _runs(mask: BoolArray, value: bool) -> list[tuple[int, int]]:
    """Maximal [start, stop) runs of ``mask == value``."""
    padded = np.concatenate(([False], mask == value, [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return [(int(a), int(b)) for a, b in zip(edges[::2], edges[1::2], strict=True)]


def clean_mask(mask: BoolArray, *, min_voiced: float = 0.1, close: float = 0.12) -> BoolArray:
    """Fill holes shorter than ``close`` s, then drop vocal islands shorter than ``min_voiced``."""
    result = mask.copy()
    for a, b in _runs(result, False):
        if a > 0 and b < len(result) and (b - a) * FRAME < close:
            result[a:b] = True
    for a, b in _runs(result, True):
        if (b - a) * FRAME < min_voiced:
            result[a:b] = False
    return result


def stem_mask(vocal: NDArray[np.float32]) -> BoolArray:
    """Voicing mask from a vocal stem: RMS above a floor and tonal (low spectral flatness)."""
    mono = vocal.mean(axis=1, dtype=np.float64)
    hop = round(FRAME * SAMPLE_RATE)
    padded = np.pad(mono, (1024, 1024))
    rms = np.asarray(
        librosa.feature.rms(y=padded, frame_length=2048, hop_length=hop, center=False)[0]
    )
    flat = np.asarray(
        librosa.feature.spectral_flatness(y=padded, n_fft=2048, hop_length=hop, center=False)[0]
    )
    count = min(len(rms), len(flat), max(1, len(mono) // hop))
    rms_db = 20 * np.log10(rms[:count] + 1e-9)
    floor = max(-52.0, float(np.percentile(rms_db, 98)) - 30.0)
    return clean_mask((rms_db > floor) & (flat[:count] < 0.35))


def heuristic_mask(features: Any, duration: float) -> BoolArray:
    """Sustained mid/high 'presence' energy share; deliberately simple and low-confidence."""
    spectrum = np.asarray(features.spectrum, dtype=np.float64) ** 2
    bin_hz = features.sr / 2048
    lo, hi, top = round(1000 / bin_hz), round(3500 / bin_hz), round(5000 / bin_hz)
    total = spectrum[round(60 / bin_hz) : top].sum(axis=0) + 1e-12
    share = spectrum[lo:hi].sum(axis=0) / total
    level = 10 * np.log10(total)
    frame_s = features.hop / features.sr
    window = max(3, round(0.4 / frame_s) | 1)
    share = np.asarray(ndimage.median_filter(share, size=window), dtype=np.float64)
    gate = level > float(np.percentile(level, 90)) - 35.0
    frames = int(np.ceil(duration / FRAME))
    times = np.arange(frames) * FRAME
    source_times = np.arange(len(share)) * frame_s
    active = np.interp(times, source_times, ((share > 0.38) & gate).astype(np.float64)) >= 0.5
    return clean_mask(np.asarray(active, dtype=np.bool_), min_voiced=0.2)


def _fractions(mask: BoolArray, starts: list[float], ends: list[float]) -> list[float]:
    csum = np.concatenate(([0], np.cumsum(mask, dtype=np.int64)))
    out: list[float] = []
    for s, e in zip(starts, ends, strict=True):
        a = min(len(mask), max(0, round(s / FRAME)))
        b = min(len(mask), max(a, round(e / FRAME)))
        out.append(round(float(csum[b] - csum[a]) / (b - a), 4) if b > a else 0.0)
    return out


def activity_from_mask(
    mask: BoolArray,
    ctx: VocalContext,
    *,
    stem_regions: list[Span],
    confidence: float,
    gap_regions: list[tuple[float, float]] | None = None,
) -> VocalActivity:
    spans = [Span(start=a * FRAME, end=min(ctx.duration, b * FRAME)) for a, b in _runs(mask, True)]
    gaps: list[Span] = []
    bounds = gap_regions or [(0.0, ctx.duration)]
    for lo, hi in bounds:
        a0, b0 = round(lo / FRAME), min(len(mask), round(hi / FRAME))
        for a, b in _runs(mask[a0:b0], False):
            if (b - a) * FRAME >= MIN_GAP - 1e-9:
                gaps.append(Span(start=(a0 + a) * FRAME, end=min(ctx.duration, (a0 + b) * FRAME)))
    beat_ends = (
        [*ctx.beats[1:], ctx.bars[-1].end if ctx.bars else ctx.duration] if ctx.beats else []
    )
    return VocalActivity(
        source="stem" if stem_regions else "heuristic",
        confidence=confidence,
        stem_regions=stem_regions,
        spans=spans,
        gaps=gaps,
        per_bar=_fractions(mask, [b.start for b in ctx.bars], [b.end for b in ctx.bars]),
        per_beat=_fractions(mask, ctx.beats, beat_ends),
    )


@dataclass
class HeuristicVocalBackend:
    name: str = "heuristic"
    version: str = "1"

    def analyze(self, ctx: VocalContext) -> VocalResult:
        mask = heuristic_mask(ctx.features, ctx.duration)
        return VocalResult(
            activity_from_mask(mask, ctx, stem_regions=[], confidence=HEURISTIC_CONFIDENCE), None
        )


@dataclass
class StemVocalBackend:
    name: str = "stems"
    version: str = "1"

    def analyze(self, ctx: VocalContext) -> VocalResult:
        mask = heuristic_mask(ctx.features, ctx.duration)
        regions: list[Span] = []
        windows: list[StemWindow] = []
        for role in ("exit", "entry"):
            start, end = stem_backend.window_frames(
                role, ctx.duration, ctx.edges.silence_head, ctx.edges.silence_tail
            )
            if end - start < SAMPLE_RATE:  # under a second of music: nothing to separate
                continue
            stems = stem_backend.separate_window(
                ctx.audio,
                ctx.pcm_sha256,
                (start, end),
                cache_root=ctx.cache_root,
                separator=ctx.separator,
            )
            local = stem_mask(stems.stems["vocals"])
            first = round(start / SAMPLE_RATE / FRAME)
            count = max(0, min(len(local), len(mask) - first))
            mask[first : first + count] = local[:count]
            region = Span(start=start / SAMPLE_RATE, end=end / SAMPLE_RATE)
            regions.append(region)
            windows.append(StemWindow(role=role, start=region.start, end=region.end))
        if not windows:
            return HeuristicVocalBackend().analyze(ctx)
        merged = _merge(regions)
        activity = activity_from_mask(
            mask,
            ctx,
            stem_regions=merged,
            confidence=STEM_CONFIDENCE,
            gap_regions=[(r.start, r.end) for r in merged],
        )
        return VocalResult(
            activity,
            StemsInfo(
                model=stem_backend.MODEL_VERSION,
                checkpoint_sha256=HTDEMUCS_SHA256,
                windows=windows,
            ),
        )


def _merge(regions: list[Span]) -> list[Span]:
    merged: list[Span] = []
    for region in sorted(regions, key=lambda r: r.start):
        if merged and region.start <= merged[-1].end:
            merged[-1] = Span(start=merged[-1].start, end=max(merged[-1].end, region.end))
        else:
            merged.append(region)
    return merged
