"""Backend contracts; implementations receive shared, deterministic features."""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from mixconsole.analysis.features import Features, FloatArray
from mixconsole.analysis.models import (
    Bar,
    Edges,
    Key,
    Loudness,
    Section,
    StemsInfo,
    VocalActivity,
)
from mixconsole.io import Audio

if TYPE_CHECKING:
    from mixconsole.analysis.backends.stems import Separator


@dataclass
class BeatResult:
    beats: list[float]
    downbeats: list[float]
    meter: int
    confidence: float


class Backend(Protocol):
    name: str
    version: str


class BeatBackend(Backend, Protocol):
    def analyze(self, features: Features, sample_rate: int) -> BeatResult: ...


class KeyBackend(Backend, Protocol):
    def analyze(self, features: Features) -> Key: ...


class LoudnessBackend(Backend, Protocol):
    def analyze(self, audio: Audio, sample_rate: int) -> tuple[Loudness, FloatArray]: ...


class SectionBackend(Backend, Protocol):
    def analyze(self, features: Features, duration: float) -> list[Section]: ...


class CueBackend(Backend, Protocol):
    def analyze(self, audio: Audio, sample_rate: int, bpm: float | None) -> Edges: ...


@dataclass
class VocalContext:
    """Everything a vocal backend needs; stems are separated lazily and cached."""

    audio: Audio
    pcm_sha256: str
    duration: float
    beats: list[float]
    bars: list[Bar]
    edges: Edges
    features: Features
    cache_root: Path | None = None
    separator: "Separator | None" = None


@dataclass
class VocalResult:
    activity: VocalActivity
    stems: StemsInfo | None


class VocalBackend(Backend, Protocol):
    def analyze(self, ctx: VocalContext) -> VocalResult: ...
