"""Signalsmith Stretch wrapper with exact output length and stable channel order."""

from itertools import pairwise
from typing import Protocol

import numpy as np
import python_stretch as ps  # pyright: ignore[reportMissingTypeStubs]

from mixconsole.io import SAMPLE_RATE, Audio


class Stretcher(Protocol):
    name: str

    def stretch(self, audio: Audio, frames: int) -> Audio: ...


class SignalsmithStretcher:
    """MIT licensed Signalsmith Stretch via the MIT Python binding."""

    name = "signalsmith@0.3.1"

    def stretch(self, audio: Audio, frames: int) -> Audio:
        if frames <= 0:
            return np.empty((0, 2), dtype=np.float32)
        if len(audio) == frames:
            return audio.copy()
        if not len(audio):
            return np.zeros((frames, 2), dtype=np.float32)
        engine = ps.Signalsmith.Stretch()  # pyright: ignore[reportUnknownMemberType]
        engine.preset(2, SAMPLE_RATE)  # pyright: ignore[reportUnknownMemberType]
        engine.timeFactor = len(audio) / frames  # pyright: ignore[reportUnknownMemberType]
        result = np.asarray(engine.process(np.ascontiguousarray(audio.T)), dtype=np.float32)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        out = np.zeros((frames, 2), dtype=np.float32)
        count = min(frames, result.shape[1])
        out[:count] = result[:, :count].T
        return out


def stretch(audio: Audio, frames: int) -> Audio:
    return SignalsmithStretcher().stretch(audio, frames)


def ramp_back(
    audio: Audio, effective_bpm: float, target_bpm: float, bars: int
) -> tuple[Audio, int]:
    """Ease a beatmatched B deck back to its source pace over two bars per percent."""
    if bars <= 0:
        return np.empty((0, 2), dtype=np.float32), 0
    engine = ps.Signalsmith.Stretch()  # pyright: ignore[reportUnknownMemberType]
    engine.preset(2, SAMPLE_RATE)  # pyright: ignore[reportUnknownMemberType]
    input_beat = SAMPLE_RATE * 60 / effective_bpm
    chunks: list[Audio] = []
    consumed = 0
    for beat in range(bars * 4):
        end = round((beat + 1) * input_beat)
        fragment = audio[consumed:end]
        if not len(fragment):
            break
        fraction = (beat + 1) / (bars * 4)
        output_bpm = target_bpm + (effective_bpm - target_bpm) * fraction
        engine.timeFactor = output_bpm / effective_bpm  # pyright: ignore[reportUnknownMemberType]
        rendered = np.asarray(engine.process(np.ascontiguousarray(fragment.T)), dtype=np.float32)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        chunks.append(np.ascontiguousarray(rendered.T))
        consumed = end
    return (np.concatenate(chunks) if chunks else np.empty((0, 2), dtype=np.float32)), consumed


def stretch_piecewise(audio: Audio, points: list[list[int]]) -> Audio:
    """Pitch-preserving beat-to-beat warp through one continuous Signalsmith state."""
    if len(points) < 2:
        return audio.copy()
    engine = ps.Signalsmith.Stretch()  # pyright: ignore[reportUnknownMemberType]
    engine.preset(2, SAMPLE_RATE)  # pyright: ignore[reportUnknownMemberType]
    chunks: list[Audio] = []
    for left, right in pairwise(points):
        source_start, target_start = left
        source_end, target_end = right
        source_count = source_end - source_start
        target_count = target_end - target_start
        if source_count <= 0 or target_count <= 0:
            raise ValueError("beat warp points must increase")
        fragment = audio[source_start:source_end]
        if len(fragment) != source_count:
            raise ValueError("beat warp exceeds source audio")
        engine.timeFactor = source_count / target_count  # pyright: ignore[reportUnknownMemberType]
        rendered = np.asarray(engine.process(np.ascontiguousarray(fragment.T)), dtype=np.float32)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        chunk = np.zeros((target_count, 2), dtype=np.float32)
        count = min(target_count, rendered.shape[1])
        chunk[:count] = rendered[:, :count].T
        chunks.append(chunk)
    return np.concatenate(chunks)
