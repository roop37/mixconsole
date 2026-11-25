# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
"""Fourth-order Linkwitz-Riley three-way crossover."""

import numpy as np
from scipy.signal import butter, sosfilt  # pyright: ignore[reportMissingTypeStubs]

from mixconsole.io import SAMPLE_RATE, Audio


def _filter(audio: Audio, frequency: float, kind: str) -> Audio:
    section = butter(2, frequency, btype=kind, fs=SAMPLE_RATE, output="sos")
    first = sosfilt(section, audio, axis=0)
    return np.asarray(sosfilt(section, first, axis=0), dtype=np.float32)


def bands(audio: Audio) -> tuple[Audio, Audio, Audio]:
    low = _filter(audio, 200, "lowpass")
    high = _filter(audio, 2500, "highpass")
    # Complementary residual makes unity gain reconstruction exact, including phase.
    mid = audio - low - high
    return low, mid, high


def isolate_mid_high(audio: Audio) -> Audio:
    """Remove bass leakage from the non-bass crossover branches during a swap."""
    return _filter(audio, 150, "highpass")
