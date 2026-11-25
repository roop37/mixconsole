"""M2 transition family registry, including the mixconsole.families entry-point group."""

import logging
from importlib.metadata import entry_points
from itertools import product
from typing import Protocol

from mixconsole.analysis.models import TrackAnalysis
from mixconsole.mixscript.models import (
    AutomationLane,
    AutomationPoint,
    Effect,
    TrackTarget,
)
from mixconsole.mixscript.models import (
    Family as FamilyName,
)
from mixconsole.plan.candidates import Candidate, PlanContext

logger = logging.getLogger(__name__)


class Family(Protocol):
    name: FamilyName
    version: str

    def applicable(
        self, a: TrackAnalysis, b: TrackAnalysis, candidate: Candidate
    ) -> bool | str: ...
    def candidates(
        self, a: TrackAnalysis, b: TrackAnalysis, ctx: PlanContext
    ) -> list[Candidate]: ...
    def automation(self, candidate: Candidate) -> tuple[list[AutomationLane], list[Effect]]: ...


class BasicFamily:
    name: FamilyName
    version = "1"

    def __init__(self, name: FamilyName) -> None:
        self.name = name

    def candidates(self, a: TrackAnalysis, b: TrackAnalysis, ctx: PlanContext) -> list[Candidate]:
        if self.name == "gapless":
            combinations = [(a.duration, 0.0, 0)]
        else:
            combinations = list(product(ctx.exits, ctx.entries, ctx.lengths))
        return [
            Candidate(
                "pending",
                self.name,
                x,
                y,
                bars,
                ctx.bpm,
                ctx.strategy if self.name == "beatmatch_blend" else "no_sync",
                beats_per_bar=a.meter,
            )
            for x, y, bars in combinations
        ]

    def applicable(self, a: TrackAnalysis, b: TrackAnalysis, candidate: Candidate) -> bool | str:
        if self.name == "gapless":
            if (
                a.edges.silence_tail > 0.05
                or b.edges.silence_head > 0.05
                or a.edges.fade_out
                or b.edges.fade_in
            ):
                return "gapless requires adjoining non-fading audio"
            if abs((a.global_bpm or 0) - (b.global_bpm or 0)) > 0.005 * (a.global_bpm or 1):
                return "gapless requires matching tempo"
            if a.key.camelot != b.key.camelot:
                return "gapless requires matching key"
        if self.name == "cut_on_downbeat" and candidate.length_bars:
            return "cut is instantaneous"
        if self.name == "trim_crossfade" and candidate.length_bars not in (1, 2, 4):
            return "crossfade length must be 1, 2 or 4 bars"
        if self.name == "beatmatch_blend" and candidate.length_bars < 4:
            return "beatmatch blend needs at least 4 bars"
        if self.name == "filter_sweep" and candidate.length_bars not in (2, 4, 8):
            return "filter sweep needs 2, 4 or 8 bars"
        if self.name == "echo_out" and candidate.length_bars not in (1, 2, 4):
            return "echo tail needs 1, 2 or 4 bars"
        return True

    def automation(self, candidate: Candidate) -> tuple[list[AutomationLane], list[Effect]]:
        if candidate.length_bars == 0:
            return [], []
        last = candidate.length_bars * candidate.beats_per_bar
        lanes = [
            AutomationLane(
                id="a_gain",
                target=TrackTarget(kind="track", track="deck_a"),
                parameter="gain",
                points=[
                    AutomationPoint(beat=0, value=1, curve="equal_power"),
                    AutomationPoint(beat=last, value=0),
                ],
            ),
            AutomationLane(
                id="b_gain",
                target=TrackTarget(kind="track", track="deck_b"),
                parameter="gain",
                points=[
                    AutomationPoint(beat=0, value=0, curve="equal_power"),
                    AutomationPoint(beat=last, value=1),
                ],
            ),
        ]
        target = TrackTarget(kind="track", track="deck_a")
        effects: list[Effect] = []
        if self.name == "beatmatch_blend":
            effects.append(
                Effect(id="bass_swap", name="bass_swap", target=target, params={"beat": last / 2})
            )
        if self.name == "filter_sweep":
            effects.append(
                Effect(
                    id="filter_a",
                    name="filter_sweep",
                    target=target,
                    params={"start_hz": 40.0, "end_hz": 8000.0},
                )
            )
        if self.name == "echo_out":
            effects.append(
                Effect(
                    id="echo_a",
                    name="echo",
                    target=target,
                    params={"tail_beats": 2.0, "feedback": 0.4},
                )
            )
        return lanes, effects


_REGISTRY: dict[str, Family] = {}
for _name in (
    "gapless",
    "trim_crossfade",
    "cut_on_downbeat",
    "beatmatch_blend",
    "filter_sweep",
    "echo_out",
):
    _REGISTRY[_name] = BasicFamily(_name)  # type: ignore[arg-type]
_loaded = False


def register(family: Family) -> None:
    if (
        family.name in _REGISTRY
        or not family.version
        or not callable(family.applicable)
        or not callable(family.candidates)
        or not callable(family.automation)
    ):
        raise ValueError("invalid or duplicate transition family")
    _REGISTRY[family.name] = family


def families() -> list[Family]:
    global _loaded
    if not _loaded:
        _loaded = True
        for entry in entry_points(group="mixconsole.families"):
            try:
                object_ = entry.load()
                family = object_() if isinstance(object_, type) else object_
                register(family)
            except Exception as exc:
                logger.warning("skipping family plugin %s: %s", entry.name, exc)
    return list(_REGISTRY.values())
