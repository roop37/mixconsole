"""Beat-synchronised filtered feedback echo."""

import numpy as np

from mixconsole.io import SAMPLE_RATE, Audio


def echo(audio: Audio, bpm: float, tail_beats: int = 4, feedback: float = 0.4) -> Audio:
    period = max(1, round(SAMPLE_RATE * 60 / bpm / 2))
    count = len(audio) + max(0, round(SAMPLE_RATE * tail_beats * 60 / bpm))
    out = np.zeros((count, 2), dtype=np.float32)
    out[: len(audio)] = audio
    previous = np.zeros(2, dtype=np.float32)
    for index in range(period, count):
        previous = 0.45 * out[index - period] + 0.55 * previous
        out[index] += feedback * previous
    return out
