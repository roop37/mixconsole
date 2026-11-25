"""Backend contracts; implementations receive shared, deterministic features."""

from dataclasses import dataclass
from typing import Protocol

from mixconsole.analysis.features import Features, FloatArray
from mixconsole.analysis.models import Edges, Key, Loudness, Section
from mixconsole.io import Audio


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
