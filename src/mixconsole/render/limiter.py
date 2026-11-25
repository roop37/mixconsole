# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
"""Deterministic master peak ceiling with a 4x true-peak probe."""

import numpy as np
from scipy.signal import resample_poly  # pyright: ignore[reportMissingTypeStubs]

from mixconsole.io import Audio


def true_peak_dbtp(audio: Audio) -> float:
    if not len(audio):
        return -120.0
    peak = float(np.max(np.abs(resample_poly(audio, 4, 1, axis=0))))
    return 20 * np.log10(max(peak, 1e-12))


def limit(audio: Audio, ceiling_dbtp: float = -1.0) -> Audio:
    peak = true_peak_dbtp(audio)
    if peak <= ceiling_dbtp:
        return audio
    return (audio * np.float32(10 ** ((ceiling_dbtp - 0.05 - peak) / 20))).astype(np.float32)
