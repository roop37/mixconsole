"""MixScript v1.1 data contract (reads v1). Audio references are content hashes, never paths."""

import json
import re
from itertools import pairwise
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

NonNegative = Annotated[float, Field(ge=0)]
Positive = Annotated[float, Field(gt=0)]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]+$")]
Family = Literal[
    "gapless",
    "trim_crossfade",
    "cut_on_downbeat",
    "beatmatch_blend",
    "stem_handoff",
    "filter_sweep",
    "echo_out",
    "vocal_over_instrumental",
]
Parameter = Literal["gain", "eq_low", "eq_mid", "eq_high", "hpf", "lpf", "delay_send"]


class Contract(BaseModel):
    """Reject unknown fields and non-finite numbers throughout the contract."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    extensions: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def namespaced_extensions(self) -> Self:
        if any(
            not re.fullmatch(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+", k) for k in self.extensions
        ):
            raise ValueError("extension keys must be namespaced, e.g. ui.colors")
        try:
            json.dumps(self.extensions, allow_nan=False)
        except (ValueError, TypeError) as exc:
            raise ValueError("extensions must contain finite JSON data") from exc
        return self


class PlayRegion(Contract):
    """Half-open source region in seconds; omitted means the complete track."""

    in_seconds: NonNegative
    out_seconds: Positive

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.in_seconds >= self.out_seconds:
            raise ValueError("play in must precede out")
        return self


class Track(Contract):
    """A track identified by SHA-256 of canonical decoded PCM (see mixconsole.io)."""

    content_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    duration: Positive = Field(description="Duration in seconds of canonical decoded audio.")
    sample_rate: Annotated[int, Field(strict=True, gt=0)]
    display_name: str | None = None
    play: PlayRegion | None = None

    @model_validator(mode="after")
    def play_bounds(self) -> Self:
        if self.play and self.play.out_seconds > self.duration:
            raise ValueError("play region exceeds track duration")
        return self


class CuePoint(Contract):
    """Zero-based source position; beats are quarter notes on that track's grid."""

    beat: NonNegative
    seconds: NonNegative


class TempoPoint(Contract):
    """Reference tempo at a transition-relative quarter-note beat; linear between points."""

    beat: NonNegative
    bpm: Positive


class TempoStrategy(Contract):
    """Tempo intent plus an explicit reference tempo map, when known."""

    strategy: Literal["none", "meet_in_middle", "ramp_b_to_a_then_back", "no_sync"]
    reference_track: Identifier
    tempo_map: list[TempoPoint] = Field(default_factory=list[TempoPoint])

    @model_validator(mode="after")
    def ordered_map(self) -> Self:
        if self.tempo_map and self.tempo_map[0].beat != 0:
            raise ValueError("tempo_map must start at beat 0")
        if any(a.beat >= b.beat for a, b in pairwise(self.tempo_map)):
            raise ValueError("tempo_map beats must be strictly increasing")
        return self


class KeyStrategy(Contract):
    """Pitch intent; permission and stem feasibility are checked by later planners."""

    strategy: Literal["none", "pitch_shift"]
    semitones: Literal[-1, 0, 1] = 0

    @model_validator(mode="after")
    def consistent_shift(self) -> Self:
        if (self.strategy == "none") != (self.semitones == 0):
            raise ValueError("none requires 0 semitones; pitch_shift requires -1 or +1")
        return self


class TrackTarget(Contract):
    """Apply automation or an effect to a whole track."""

    kind: Literal["track"]
    track: Identifier


class StemTarget(Contract):
    """Apply automation or an effect to a separated stem."""

    kind: Literal["stem"]
    track: Identifier
    stem: Literal["drums", "bass", "other", "vocals"]


Target = Annotated[TrackTarget | StemTarget, Field(discriminator="kind")]


class AutomationPoint(Contract):
    """Beat is relative to transition start on the reference grid; curve leads to next point."""

    beat: NonNegative
    value: float
    curve: Literal["step", "linear", "equal_power", "exponential"] = "linear"


class AutomationLane(Contract):
    """Gain/send use linear amplitude, EQ uses dB, and HPF/LPF use Hz."""

    id: Identifier | None = None

    target: Target
    parameter: Parameter
    points: list[AutomationPoint] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_points(self) -> Self:
        if any(a.beat >= b.beat for a, b in pairwise(self.points)):
            raise ValueError("automation beats must be strictly increasing")
        for point in self.points:
            if self.parameter in ("gain", "delay_send") and point.value < 0:
                raise ValueError("gain and delay_send must be non-negative")
            if self.parameter in ("hpf", "lpf") and not 0 < point.value < 22050:
                raise ValueError("filter frequency must be between 0 and 22050 Hz")
        for a, b in pairwise(self.points):
            if a.curve == "exponential" and (a.value <= 0 or b.value <= 0):
                raise ValueError("exponential segments require positive endpoints")
        return self


class Effect(Contract):
    """Named effect with scalar parameters; rendering support arrives after M0."""

    id: Identifier | None = None

    name: Annotated[str, Field(min_length=1)]
    target: Target
    params: dict[str, float | str | bool] = Field(default_factory=dict)


class RejectedCandidate(Contract):
    """A candidate ID and a human-readable reason for rejecting it."""

    candidate_id: Identifier
    family: Family
    reason: Annotated[str, Field(min_length=1)]
    score: float | None = None


class Explanation(Contract):
    """Human-readable planning rationale."""

    chosen_because: Annotated[str, Field(min_length=1)]
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    rejected_candidates: list[RejectedCandidate] = Field(default_factory=list[RejectedCandidate])


class CandidateSummary(Contract):
    """Inspectable alternative; preview is an artifact reference, not audio bytes."""

    id: Identifier
    family: Family
    exit: CuePoint
    entry: CuePoint
    length_bars: Annotated[int, Field(strict=True, ge=0)]
    score: float
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    preview_artifact: str | None = None


class Transition(Contract):
    """An ordered handoff between two track IDs."""

    id: Identifier | None = None

    from_track: Identifier
    to_track: Identifier
    family: Family
    exit: CuePoint
    entry: CuePoint
    length_bars: Annotated[int, Field(strict=True, ge=0)]
    beats_per_bar: Annotated[int, Field(strict=True, gt=0)] = Field(
        default=4, description="Quarter-note beats per reference bar."
    )
    tempo: TempoStrategy
    key: KeyStrategy
    automation: list[AutomationLane] = Field(default_factory=list[AutomationLane])
    effects: list[Effect] = Field(default_factory=list[Effect])
    explanation: Explanation | None = None
    candidates: list[CandidateSummary] = Field(default_factory=list[CandidateSummary])
    locks: frozenset[str] = Field(default_factory=frozenset)

    @field_serializer("locks")
    def ordered_locks(self, value: frozenset[str]) -> list[str]:
        return sorted(value)

    @model_validator(mode="after")
    def valid_targets(self) -> Self:
        allowed = {"exit", "entry", "length_bars", "family", "tempo", "key"}
        allowed.update(lane.id for lane in self.automation if lane.id is not None)
        if self.locks - allowed:
            raise ValueError("locks must name transition fields or existing lane ids")
        pair = {self.from_track, self.to_track}
        if len(pair) != 2:
            raise ValueError("a transition must reference two different tracks")
        if self.tempo.reference_track not in pair:
            raise ValueError("tempo reference must belong to the transition")
        for target in [lane.target for lane in self.automation] + [e.target for e in self.effects]:
            if target.track not in pair:
                raise ValueError("automation/effect target must belong to the transition")
        identities = [(lane.target.model_dump_json(), lane.parameter) for lane in self.automation]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate automation lane for target and parameter")
        return self


class Provenance(Contract):
    """Versions and random seed needed to reproduce planning decisions."""

    analysis_backends: dict[str, Annotated[str, Field(min_length=1)]]
    scorer_version: Annotated[str, Field(min_length=1)]
    seed: Annotated[int, Field(strict=True, ge=0)]


class MixScript(Contract):
    """Versioned, shareable transition specification, independent of audio paths."""

    version: Literal["mixscript/v1", "mixscript/v1.1"]
    tracks: dict[Identifier, Track] = Field(min_length=1)
    transitions: list[Transition]
    provenance: Provenance
    explanation: Explanation | None = None

    @model_validator(mode="after")
    def valid_references(self) -> Self:
        ids = list(self.tracks)
        for transition in self.transitions:
            objects = [
                transition,
                *transition.automation,
                *transition.effects,
                *transition.candidates,
            ]
            for obj in objects:
                if obj.id is None:
                    if self.version == "mixscript/v1.1":
                        raise ValueError("v1.1 transitions, lanes and effects require ids")
                else:
                    ids.append(obj.id)
            if len(ids) != len(set(ids)):
                raise ValueError("ids must be unique within the script")
            for track_id, cue in (
                (transition.from_track, transition.exit),
                (transition.to_track, transition.entry),
            ):
                if track_id not in self.tracks:
                    raise ValueError(f"unknown track: {track_id}")
                track = self.tracks[track_id]
                if (
                    track.play
                    and not track.play.in_seconds <= cue.seconds <= track.play.out_seconds
                ):
                    raise ValueError("cue outside track play region")
                if cue.seconds > self.tracks[track_id].duration:
                    raise ValueError(f"cue exceeds duration of track: {track_id}")
        return self
