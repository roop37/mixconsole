"""Sample-position gain curves."""

from itertools import pairwise

import numpy as np
from numpy.typing import NDArray

from mixconsole.mixscript.models import AutomationLane


def curve(count: int, kind: str, *, incoming: bool = False) -> NDArray[np.float32]:
    if count <= 0:
        return np.empty(0, dtype=np.float32)
    phase = np.linspace(0, 1, count, dtype=np.float64)
    if not incoming:
        phase = 1 - phase
    if kind == "equal_power":
        gain = np.sin(phase * np.pi / 2)
    elif kind == "exponential":
        gain = np.maximum(phase, 0.0001) ** 2
    elif kind == "step":
        gain = (phase > 0).astype(np.float64)
    else:
        gain = phase
    return gain.astype(np.float32)


def lane_curve(lane: AutomationLane, count: int, bpm: float) -> NDArray[np.float32]:
    """Evaluate a MixScript gain lane at each output sample."""
    result = np.full(count, lane.points[-1].value, dtype=np.float32)
    for left, right in pairwise(lane.points):
        start = max(0, min(count, round(left.beat * 60 / bpm * 44100)))
        end = max(start, min(count, round(right.beat * 60 / bpm * 44100)))
        if end <= start:
            continue
        phase = np.linspace(0, 1, end - start, endpoint=False, dtype=np.float64)
        if left.curve == "step":
            values = np.full_like(phase, left.value)
        elif left.curve == "exponential":
            values = left.value * (right.value / left.value) ** phase
        elif left.curve == "equal_power":
            values = left.value * np.cos(phase * np.pi / 2) + right.value * np.sin(
                phase * np.pi / 2
            )
        else:
            values = left.value + (right.value - left.value) * phase
        result[start:end] = values.astype(np.float32)
    return result
