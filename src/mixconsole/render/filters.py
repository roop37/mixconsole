# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
"""Biquad high/low pass with smoothly changing cutoff."""

import numpy as np
from scipy.signal import butter, sosfilt  # pyright: ignore[reportMissingTypeStubs]

from mixconsole.io import SAMPLE_RATE, Audio


def sweep(audio: Audio, start_hz: float, end_hz: float, kind: str) -> Audio:
    out = np.zeros_like(audio)
    state = np.zeros((1, 2, 2), dtype=np.float64)
    # 48-sample blocks bound coefficient movement; overlap in cutoff is continuous.
    for start in range(0, len(audio), 48):
        end = min(len(audio), start + 48)
        fraction = (start + end) / (2 * max(1, len(audio)))
        frequency = start_hz * (end_hz / start_hz) ** fraction
        sos = butter(2, frequency, btype=kind, fs=SAMPLE_RATE, output="sos")
        values, state = sosfilt(sos, audio[start:end], axis=0, zi=state)
        out[start:end] = values
    return out
