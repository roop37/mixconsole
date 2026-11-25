"""Bounded two-track transition search over M1 phrase and edge annotations."""

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from mixconsole.analysis.models import TrackAnalysis
from mixconsole.config import Settings
from mixconsole.mixscript.models import Family, RejectedCandidate

LENGTHS = (0, 1, 2, 4, 8, 16, 32)
TempoName = Literal["none", "meet_in_middle", "ramp_b_to_a_then_back", "no_sync"]


@dataclass
class Candidate:
    id: str
    family: Family
    exit_seconds: float
    entry_seconds: float
    length_bars: int
    bpm: float | None
    tempo_strategy: TempoName
    beats_per_bar: int = 4
    score: float = 0.0
    variant: str = ""
    params: dict[str, float] = field(default_factory=dict[str, float])
    veto: str | None = None
    seam_gain_db: float = 0.0
    features: dict[str, float] = field(default_factory=dict[str, float])

    @property
    def duration(self) -> float:
        if self.bpm:
            return self.length_bars * self.beats_per_bar * 60 / self.bpm
        return self.length_bars * 2.0


@dataclass
class PlanContext:
    exits: list[float]
    entries: list[float]
    lengths: tuple[int, ...]
    bpm: float | None
    strategy: TempoName


@dataclass
class PlanResult:
    candidates: list[Candidate]
    rejected: list[RejectedCandidate]
    stem_note: str = ""


STEM_FAMILY_NAMES = ("stem_handoff", "vocal_over_instrumental")
PLAIN_FAMILY_NAMES = (
    "beatmatch_blend",
    "filter_sweep",
    "echo_out",
    "cut_on_downbeat",
    "trim_crossfade",
)


def effective_tempo(b: TrackAnalysis, bpm: float | None) -> float:
    """B's tempo after the half/double-time choice closest to the reference ``bpm``."""
    reference = bpm or 120.0
    if not b.global_bpm:
        return reference
    return min(
        (b.global_bpm * scale for scale in (0.5, 1.0, 2.0)), key=lambda v: abs(v - reference)
    )


def cues(analysis: TrackAnalysis, *, exit_track: bool) -> list[float]:
    """Phrase cues in the relevant 40 percent, plus a useful edge downbeat."""
    bound = analysis.duration * (0.6 if exit_track else 0.4)
    phrase = [
        p.start for p in analysis.phrases if (p.start >= bound if exit_track else p.start <= bound)
    ]
    edge = (
        analysis.duration - analysis.edges.silence_tail
        if exit_track
        else analysis.edges.silence_head
    )
    beats = (
        [t for t in analysis.downbeats if t <= edge + 0.02]
        if exit_track
        else [t for t in analysis.downbeats if t >= edge - 0.02]
    )
    if beats:
        phrase.append(beats[-1] if exit_track else beats[0])
    if not phrase:
        phrase.append(max(0.0, bound) if exit_track else min(analysis.duration, bound))
    return sorted(set(phrase))


def has_beat_grid(analysis: TrackAnalysis) -> bool:
    if analysis.global_bpm is None or not analysis.beats:
        return False
    bars = analysis.arrays.get("bar_energy")
    if bars is None or not len(bars):
        return analysis.beat_confidence > 0.1
    return analysis.beat_confidence > 0.1 or float(np.median(bars[:, 1])) >= 0.1


def tempo_choice(
    a: TrackAnalysis, b: TrackAnalysis, settings: Settings
) -> tuple[float | None, TempoName]:
    if a.global_bpm is None or b.global_bpm is None or not has_beat_grid(a) or not has_beat_grid(b):
        return a.global_bpm or b.global_bpm, "no_sync"
    ratios = [
        (abs(a.global_bpm - b.global_bpm * scale) / a.global_bpm, scale)
        for scale in (0.5, 1.0, 2.0)
    ]
    difference, _scale = min(ratios)
    if difference > settings.max_stretch:
        return a.global_bpm, "no_sync"
    if difference < 0.005:
        return a.global_bpm, "none"
    return a.global_bpm, "ramp_b_to_a_then_back"


def plan_pair(
    a: TrackAnalysis,
    b: TrackAnalysis,
    settings: Settings,
    *,
    style: str = "auto",
    locks: dict[str, object] | None = None,
) -> PlanResult:
    """Generate a bounded set. Each pruned proposal carries a concrete reason."""
    from mixconsole.plan.families import families
    from mixconsole.score.heuristic import score, total

    locked = locks or {}
    bpm, strategy = tempo_choice(a, b, settings)
    result: list[Candidate] = []
    rejected: list[RejectedCandidate] = []
    ctx = PlanContext(cues(a, exit_track=True), cues(b, exit_track=False), LENGTHS, bpm, strategy)
    for family in families():
        proposed: list[Candidate] = []
        if family.name in STEM_FAMILY_NAMES and settings.stems == "off":
            rejected.append(
                RejectedCandidate(
                    candidate_id=f"{family.name}_na", family=family.name, reason="stems disabled"
                )
            )
            continue
        unavailable = getattr(family, "unavailable", None)
        reason_na = unavailable(a, b) if callable(unavailable) else None
        if reason_na:
            rejected.append(
                RejectedCandidate(
                    candidate_id=f"{family.name}_na", family=family.name, reason=str(reason_na)
                )
            )  # type: ignore[arg-type]
            continue
        for candidate in family.candidates(a, b, ctx):
            ident = f"c{len(result) + len(proposed) + len(rejected):05d}"
            candidate.id = ident
            reason = family.applicable(a, b, candidate)
            if reason is True:
                from mixconsole.plan.constraints import rejection_reason

                reason = rejection_reason(a, b, candidate, settings, locked)
            if reason is not None and reason is not False:
                rejected.append(
                    RejectedCandidate(candidate_id=ident, family=family.name, reason=str(reason))
                )  # type: ignore[arg-type]
                continue
            candidate.features = score(candidate, a, b, style)
            candidate.score = total(candidate.features, style)
            proposed.append(candidate)
        proposed.sort(key=lambda c: (-c.score, c.exit_seconds, c.entry_seconds, c.length_bars))
        result.extend(proposed[: settings.candidates_per_family])
    note = {"off": "Stems: off (stem families not applicable: stems disabled)."}.get(
        settings.stems, "Stems: on (stem families always compete)."
    )
    if settings.stems == "auto":
        result, note = _gate_stems(result, rejected, a, b, settings)
    result.sort(key=lambda c: (-c.score, c.id))
    return PlanResult(result[: settings.max_candidates], rejected, note)


def _gate_stems(
    result: list[Candidate],
    rejected: list[RejectedCandidate],
    a: TrackAnalysis,
    b: TrackAnalysis,
    settings: Settings,
) -> tuple[list[Candidate], str]:
    """``stems=auto``: keep stem candidates only with a concrete reason and a clear score win."""
    from mixconsole.score.heuristic import key_compatibility, key_reliability

    stem = [c for c in result if c.family in STEM_FAMILY_NAMES]
    if not stem:
        return result, "Stems: auto (no stem candidate applicable)."
    plain = [c for c in result if c.family in PLAIN_FAMILY_NAMES]
    key = key_compatibility(a, b)
    reliability = key_reliability(a, b)
    reasons: list[str] = []
    if key < 0.2 and reliability > 0:
        reasons.append(f"key clash (compatibility {key:.2f}, key reliability {reliability:.2f})")
    blends = ("beatmatch_blend", "filter_sweep")
    collided = any(r.family in blends and r.reason.startswith("lead vocals") for r in rejected)
    if collided and not any(c.family in blends for c in result):
        reasons.append("measured vocal collision that no plain blend avoids")
    best_stem = max(c.score for c in stem)
    best_plain = max((c.score for c in plain), default=None)
    if not reasons:
        decline = "no key clash or unavoidable vocal collision"
    elif best_plain is not None and best_stem < best_plain + settings.stems_auto_margin:
        decline = (
            f"best stem {best_stem:.3f} does not beat best plain {best_plain:.3f} "
            f"by {settings.stems_auto_margin:.2f} (reason: {'; '.join(reasons)})"
        )
    else:
        beaten = "no plain candidate" if best_plain is None else f"best plain {best_plain:.3f}"
        return result, (
            f"Stems: auto allowed ({'; '.join(reasons)}); best stem {best_stem:.3f} beats {beaten} "
            f"by >= {settings.stems_auto_margin:.2f}."
        )
    seen: list[Family] = list(dict.fromkeys(c.family for c in stem))
    rejected.extend(
        RejectedCandidate(
            candidate_id=f"{family}_auto", family=family, reason=f"stems auto: {decline}"
        )
        for family in seen
    )
    return [
        c for c in result if c.family not in STEM_FAMILY_NAMES
    ], f"Stems: auto declined ({decline})."
