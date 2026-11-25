"""UI artifacts: multi-resolution waveform peaks (audiowaveform JSON + .dat), lane data, previews.

Peaks follow BBC audiowaveform data format version 2 (8-bit, mono mix of the channels with
min/max pairs per pixel), which wavesurfer.js reads directly (JSON via ``peaks``/``fetch`` and
the binary ``.dat`` via the audiowaveform loader). Lower ``samples_per_pixel`` is more detail.
"""

import struct
from pathlib import Path

import numpy as np
from pydantic import BaseModel

from mixconsole.analysis.models import TrackAnalysis
from mixconsole.io import SAMPLE_RATE, Audio, load_audio, write_audio

RESOLUTIONS = (256, 1024, 4096, 16384)


class Peaks(BaseModel):
    """audiowaveform JSON v2 (wavesurfer-compatible); ``data`` is [min, max, ...] int8 pairs."""

    version: int = 2
    channels: int = 1
    sample_rate: int = SAMPLE_RATE
    samples_per_pixel: int
    bits: int = 8
    length: int
    data: list[int]


class Span2(BaseModel):
    start: float
    end: float


class SectionLane(Span2):
    label: str | None
    source: str


class PhraseLane(BaseModel):
    start: float
    start_bar: int
    length_bars: int
    confidence: float


class Lanes(BaseModel):
    """Everything the timeline draws, in seconds, taken directly from the analysis."""

    duration: float
    bpm: float | None
    meter: int
    beats: list[float]
    downbeats: list[float]
    bars: list[Span2]
    phrases: list[PhraseLane]
    sections: list[SectionLane]
    vocals: list[Span2]
    vocal_source: str | None
    bar_energy: list[float]


def peak_levels(samples: Audio) -> dict[int, np.ndarray]:
    mono = samples.mean(axis=1) if samples.ndim == 2 else samples
    levels: dict[int, np.ndarray] = {}
    for spp in RESOLUTIONS:
        count = -(-len(mono) // spp)
        padded = np.zeros(count * spp, dtype=np.float32)
        padded[: len(mono)] = mono
        blocks = padded.reshape(count, spp)
        low = np.clip(np.floor(blocks.min(axis=1) * 128), -128, 127)
        high = np.clip(np.ceil(blocks.max(axis=1) * 127), -128, 127)
        levels[spp] = np.stack([low, high], axis=1).astype(np.int8)
    return levels


def dat_bytes(spp: int, pairs: np.ndarray) -> bytes:
    """audiowaveform v2 header: version, flags(bit0=8-bit), rate, spp, length, channels."""
    header = struct.pack("<iIiiIi", 2, 1, SAMPLE_RATE, spp, len(pairs), 1)
    return header + pairs.astype(np.int8).tobytes()


def write_peaks(folder: Path, samples: Audio) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for spp, pairs in peak_levels(samples).items():
        payload = Peaks(samples_per_pixel=spp, length=len(pairs), data=pairs.ravel().tolist())
        (folder / f"{spp}.json").write_text(payload.model_dump_json(), encoding="utf-8")
        (folder / f"{spp}.dat").write_bytes(dat_bytes(spp, pairs))


def ensure_peaks(folder: Path, source: Path) -> None:
    if all((folder / f"{spp}.{ext}").is_file() for spp in RESOLUTIONS for ext in ("json", "dat")):
        return
    write_peaks(folder, load_audio(source).samples)


def lanes_from(analysis: TrackAnalysis) -> Lanes:
    energy = analysis.arrays.get("bar_energy")
    per_bar: list[float] = (
        [float(v) for v in energy.sum(axis=1)] if energy is not None and energy.ndim == 2 else []
    )
    vocal = analysis.vocal_activity
    return Lanes(
        duration=analysis.duration,
        bpm=analysis.global_bpm,
        meter=analysis.meter,
        beats=analysis.beats,
        downbeats=analysis.downbeats,
        bars=[Span2(start=b.start, end=b.end) for b in analysis.bars],
        phrases=[
            PhraseLane(
                start=p.start,
                start_bar=p.start_bar,
                length_bars=p.length_bars,
                confidence=p.confidence,
            )
            for p in analysis.phrases
        ],
        sections=[
            SectionLane(start=s.start, end=s.end, label=s.label, source=s.source)
            for s in analysis.sections
        ],
        vocals=[Span2(start=s.start, end=s.end) for s in vocal.spans] if vocal else [],
        vocal_source=vocal.source if vocal else None,
        bar_energy=per_bar,
    )


def track_preview(folder: Path, source: Path) -> Path:
    """Full-length preview encode (Opus when ffmpeg is present, else 32-bit-float WAV)."""
    from mixconsole.service import encode_preview

    folder.mkdir(parents=True, exist_ok=True)
    for name in ("preview.opus", "preview.wav"):
        if (folder / name).is_file():
            return folder / name
    wav = folder / "preview.wav"
    write_audio(wav, load_audio(source).samples)
    return encode_preview(wav)
