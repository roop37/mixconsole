"""Silence and edge cues; amplitude gate is -60 dBFS across either channel."""

import numpy as np

from mixconsole.analysis.models import Edges
from mixconsole.io import Audio


class EdgeCueBackend:
    name = "edges"
    version = "1"  # outputs unchanged by the M1H memory work

    def analyze(self, audio: Audio, sample_rate: int, bpm: float | None) -> Edges:
        # Per-channel abs avoids a full stereo temporary; amplitude stays float32.
        amplitude = np.maximum(np.abs(audio[:, 0]), np.abs(audio[:, -1]))
        active = np.flatnonzero(amplitude > 0.001)
        if not len(active):
            return Edges(
                silence_head=len(audio) / sample_rate,
                silence_tail=0,
                fade_in=False,
                fade_out=False,
                hard_ending=False,
            )
        first, last = int(active[0]), int(active[-1]) + 1
        block = max(1, sample_rate // 10)
        squared = np.square(amplitude, dtype=np.float32)
        power = (
            np.pad(squared, (0, (-len(audio)) % block))
            .reshape(-1, block)
            .mean(axis=1, dtype=np.float64)
        )
        del squared
        lo, hi = first // block, min(len(power), (last + block - 1) // block)
        music = power[lo:hi]
        width = min(len(music) // 2, 40)

        def fades(values: np.ndarray[tuple[int], np.dtype[np.float64]]) -> bool:
            if len(values) < 10 or np.max(values) < 1e-8:
                return False
            # Quartile medians suppress individual drum hits.
            levels = np.array([np.median(v) for v in np.array_split(values, 4)])
            return bool(
                levels[0] < levels[-1] * 0.3 and np.corrcoef(np.arange(4), levels)[0, 1] > 0.85
            )

        fade_in = fades(music[:width])
        fade_out = fades(music[-width:][::-1])
        beat = round(sample_rate * (60 / bpm if bpm else 0.5))
        before = float(np.mean(amplitude[max(first, last - beat) : last] ** 2))
        terminal = float(np.mean(amplitude[max(first, last - sample_rate // 100) : last] ** 2))
        hard = not fade_out and before > 1e-6 and (terminal > before * 0.1 or last < len(audio))
        return Edges(
            silence_head=first / sample_rate,
            silence_tail=(len(audio) - last) / sample_rate,
            fade_in=fade_in,
            fade_out=fade_out,
            hard_ending=hard,
        )
