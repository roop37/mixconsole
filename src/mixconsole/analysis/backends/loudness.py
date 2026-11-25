"""K-weighted LUFS, ungated three-second short-term LUFS, 4x true-peak estimate."""

from importlib import import_module
from typing import Any

import numpy as np

from mixconsole.analysis.features import FloatArray, signal
from mixconsole.analysis.models import ArrayRef, Loudness
from mixconsole.io import Audio

pyloudnorm: Any = import_module("pyloudnorm")


BLOCK_SECONDS = 0.1


def gated_integrated(block_power: FloatArray) -> float:
    """BS.1770-4 integrated loudness from 100 ms K-weighted channel-summed mean powers.

    Gating blocks are 400 ms with 75 % overlap (4 consecutive 100 ms blocks), an absolute
    gate at -70 LUFS and a relative gate 10 LU below the absolutely gated mean.
    """
    if len(block_power) < 4:
        return float("-inf")
    window = np.convolve(block_power, np.ones(4) / 4, mode="valid")
    with np.errstate(divide="ignore"):
        levels = -0.691 + 10 * np.log10(window)
    above = window[levels > -70]
    if not len(above):
        return float("-inf")
    relative = -0.691 + 10 * np.log10(above.mean()) - 10
    gated = window[(levels > -70) & (levels > relative)]
    return float(-0.691 + 10 * np.log10(gated.mean())) if len(gated) else float("-inf")


class PyloudnormBackend:
    """pyloudnorm's K-weighting filters, applied once per channel with 100 ms reduction.

    Memory is O(one channel) instead of several full stereo float64 copies, and the
    track is filtered once for both integrated and short-term loudness.
    """

    name = "pyloudnorm"
    version = "2"

    def analyze(self, audio: Audio, sample_rate: int) -> tuple[Loudness, FloatArray]:
        meter = pyloudnorm.Meter(sample_rate)
        block = round(BLOCK_SECONDS * sample_rate)
        blocks = -(-len(audio) // block)
        power = np.zeros(blocks, dtype=np.float64)
        for channel in range(audio.shape[1]):
            weighted = audio[:, channel].astype(np.float64)
            for stage in meter._filters.values():
                weighted = stage.apply_filter(weighted)
            squared = np.pad(weighted**2, (0, blocks * block - len(weighted)))
            power += squared.reshape(blocks, block).sum(axis=1)
            del weighted, squared
        # Mean power per 100 ms block (the final partial block is zero-padded).
        block_power = power / block
        integrated = gated_integrated(block_power)
        # Short-term: forward-looking 3 s (30 blocks) every 100 ms, silence-padded at EOF.
        cumulative = np.concatenate(([0.0], np.cumsum(block_power)))
        starts = np.arange(blocks)
        stops = np.minimum(starts + 30, blocks)
        means = (cumulative[stops] - cumulative[starts]) / 30
        curve = np.maximum(-120, -0.691 + 10 * np.log10(np.maximum(means, 1e-12)))
        peak = 0.0
        # Overlapping chunks bound peak-estimation memory and retain filter context.
        for start in range(0, len(audio), sample_rate * 10):
            chunk = audio[max(0, start - 64) : min(len(audio), start + sample_rate * 10 + 64)]
            peak = max(peak, float(np.max(abs(signal.resample_poly(chunk, 4, 1, axis=0)))))
        return Loudness(
            integrated_lufs=integrated if np.isfinite(integrated) else None,
            true_peak_dbtp=20 * float(np.log10(peak)) if peak else None,
            short_term_lufs=ArrayRef(key="short_term_lufs", shape=[len(curve)]),
        ), np.asarray(curve, dtype=np.float64)
