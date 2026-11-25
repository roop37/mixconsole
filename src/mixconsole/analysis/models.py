"""Versioned, finite analysis contract. Times are seconds; bar indices are zero based."""

import json
from itertools import pairwise
from typing import Annotated, Literal, Self

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

Probability = Annotated[float, Field(ge=0, le=1)]
Time = Annotated[float, Field(ge=0)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ArrayRef(Model):
    """Numeric float64 array in the sibling NPZ; no pickle or object arrays."""

    file: str = "analysis.npz"
    key: str
    shape: list[int]
    columns: list[str] = Field(default_factory=list)


class TempoSegment(Model):
    start: Time
    end: Time
    bpm: Annotated[float, Field(gt=0)]


class Bar(Model):
    start: Time
    end: Time


class Phrase(Model):
    start: Time
    start_bar: Annotated[int, Field(ge=0)]
    length_bars: Literal[4, 8, 16]
    confidence: Probability


class Section(Model):
    start: Time
    end: Time
    label: str | None = None
    source: str


class KeyAlternative(Model):
    tonic: Annotated[int, Field(ge=0, le=11)]
    mode: Literal["major", "minor"]
    camelot: Annotated[str, Field(pattern=r"^(?:[1-9]|1[0-2])[AB]$")]
    confidence: Probability


class Key(KeyAlternative):
    alternatives: list[KeyAlternative] = Field(min_length=3, max_length=3)


class Loudness(Model):
    # Silence is null, never non-standard JSON Infinity.
    integrated_lufs: float | None
    true_peak_dbtp: float | None
    short_term_lufs: ArrayRef
    hop_seconds: float = 0.1
    window_seconds: float = 3.0


class Edges(Model):
    silence_head: Time
    silence_tail: Time
    fade_in: bool
    fade_out: bool
    hard_ending: bool


class Span(Model):
    """Half-open [start, end) interval in seconds."""

    start: Time
    end: Time

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.start >= self.end:
            raise ValueError("span start must precede end")
        return self


class VocalActivity(Model):
    """Lead-vocal presence. ``per_bar``/``per_beat`` are the active fraction of each bar/beat.

    ``source`` is "stem" when every value comes from a separated vocal stem and "heuristic"
    when any part comes from the low-confidence spectral estimate; ``stem_regions`` lists
    the stem-derived windows. ``gaps`` are vocal-free spans of at least 300 ms.
    """

    source: Literal["stem", "heuristic"]
    confidence: Probability
    stem_regions: list[Span] = Field(default_factory=list[Span])
    spans: list[Span]
    gaps: list[Span]
    per_bar: list[Probability]
    per_beat: list[Probability]


class StemWindow(Model):
    role: Literal["exit", "entry"]
    start: Time
    end: Time


class StemsInfo(Model):
    """Separated windows (exit window of the outgoing role, entry window of the incoming role).

    The stems themselves live in the stem cache keyed by (pcm_sha256, window, model).
    """

    model: str
    checkpoint_sha256: Digest
    windows: list[StemWindow]


class TrackAnalysis(Model):
    version: Literal["track-analysis/v1"] = "track-analysis/v1"
    file: str
    file_sha256: Digest
    pcm_sha256: Digest
    duration: Annotated[float, Field(gt=0)]
    sample_rate: Annotated[int, Field(gt=0)]
    beats: list[Time]
    beat_confidence: Probability
    downbeats: list[Time]
    meter: Literal[3, 4]
    tempo_map: list[TempoSegment]
    global_bpm: Annotated[float, Field(gt=0)] | None
    bars: list[Bar]
    phrases: list[Phrase]
    sections: list[Section]
    key: Key
    loudness: Loudness
    bar_energy: ArrayRef
    edges: Edges
    vocal_activity: VocalActivity | None = None
    stems: StemsInfo | None = None
    backend_versions: dict[str, str]
    analysis_seed: Annotated[int, Field(ge=0)] = 0
    arrays_sha256: Digest | None = None
    _arrays: dict[str, NDArray[np.float64]] = PrivateAttr(default_factory=dict)
    _cache_hit: bool = PrivateAttr(default=False)

    @property
    def arrays(self) -> dict[str, NDArray[np.float64]]:
        """Hydrated curves: short_term_lufs (floor -120), bar_energy (N x 5)."""
        return self._arrays

    @property
    def cache_hit(self) -> bool:
        return self._cache_hit

    def mark_cache_hit(self) -> None:
        self._cache_hit = True

    @model_validator(mode="after")
    def musical_order(self) -> Self:
        for values in (self.beats, self.downbeats, [p.start for p in self.phrases]):
            if any(a >= b for a, b in pairwise(values)):
                raise ValueError("musical timestamps must be strictly increasing")
            if any(t >= self.duration for t in values):
                raise ValueError("musical timestamps must precede duration")
        if not set(self.downbeats) <= set(self.beats):
            raise ValueError("downbeats must be beats")
        if not {p.start for p in self.phrases} <= set(self.downbeats):
            raise ValueError("phrase starts must be downbeats")
        for p in self.phrases:
            if p.start_bar >= len(self.bars) or self.bars[p.start_bar].start != p.start:
                raise ValueError("phrase start_bar must identify its bar")
        for spans in (self.bars, self.sections, self.tempo_map):
            if any(s.start >= s.end or s.end > self.duration for s in spans):
                raise ValueError("invalid analysis interval")
            if any(a.end > b.start for a, b in pairwise(spans)):
                raise ValueError("analysis intervals overlap")
        return self


def schema_json() -> str:
    schema = TrackAnalysis.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "urn:mixconsole:track-analysis:v1"
    return json.dumps(schema, indent=2, sort_keys=True, allow_nan=False) + "\n"
