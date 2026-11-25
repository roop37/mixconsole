"""Deterministic 'perfect separator' for synthetic tracks (no model, no weights).

Each synthetic track is rendered once per component (drums, bass, pad, vocals) from the
same seed, so the components are exact ground-truth stems of the mix.
"""

from functools import cache

import numpy as np
from numpy.typing import NDArray

from mixconsole.testing.synth import generate_track

Audio = NDArray[np.float32]


class OracleSeparator:
    name = "htdemucs"
    version = "oracle@1"

    def __init__(self) -> None:
        self.items: list[tuple[Audio, dict[str, Audio]]] = []
        self.calls = 0

    def add(self, full: Audio, parts: dict[str, Audio]) -> None:
        self.items.append((full, parts))

    def separate(self, audio: Audio, start_frame: int) -> dict[str, Audio]:
        self.calls += 1
        for full, parts in self.items:
            segment = full[start_frame : start_frame + len(audio)]
            if len(segment) == len(audio) and np.array_equal(segment, audio):
                return {n: p[start_frame : start_frame + len(audio)] for n, p in parts.items()}
        raise AssertionError("window does not belong to a registered oracle track")


@cache
def _render(
    bpm: float, bars: int, vocal_bars: tuple[int, ...], key: str, seed: int, fade: float
) -> tuple[Audio, dict[str, Audio]]:
    common = {"bpm": bpm, "bars": bars, "key": key, "seed": seed}
    full, _ = generate_track(**common, vocal_bars=vocal_bars)
    drums, _ = generate_track(**common, bass=False, pad=False)
    bass, _ = generate_track(**common, percussion="none", pad=False)
    other, _ = generate_track(**common, percussion="none", bass=False)
    voice, _ = generate_track(
        **common, percussion="none", bass=False, pad=False, vocal_bars=vocal_bars
    )
    ramp = np.ones(len(full), dtype=np.float32)
    count = round(fade * 44100)
    ramp[-count:] = np.linspace(1, 0, count, dtype=np.float32)
    parts = {
        "drums": drums * ramp[:, None],
        "bass": bass * ramp[:, None],
        "other": other * ramp[:, None],
        "vocals": voice * ramp[:, None],
    }
    return full * ramp[:, None], parts


def oracle_track(
    oracle: OracleSeparator,
    *,
    bpm: float = 128,
    bars: int = 32,
    vocal_bars: tuple[int, ...] = (),
    key: str = "C major",
    seed: int = 0,
    fade: float = 6.0,
) -> Audio:
    """Return a synthetic mix (with a fade-out so it is not a 'hard ending') and register stems.

    Rendering is memoised per argument set, so fixtures sharing a track pay for it once.
    """
    mix, parts = _render(bpm, bars, vocal_bars, key, seed, fade)
    oracle.add(mix, parts)
    return mix
