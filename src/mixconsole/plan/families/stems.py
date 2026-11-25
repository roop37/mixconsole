"""Stem-aware families: ``stem_handoff`` and ``vocal_over_instrumental``.

Both need Demucs stems of A's exit window and B's entry window; without the extra they
report one "not applicable" reason instead of candidates. Schedules guarantee by
construction (and verification re-measures on rendered stems) that

* A's and B's lead vocals never overlap (A's vocal leaves at a lyric gap >= 300 ms, B's
  enters at a vocal onset at least half a beat later),
* A's and B's basslines never overlap (a bar-aligned swap with a 1/8-beat gap),
* nothing is cut mid-word on the outgoing side.

``stem_handoff`` has two variants. ``classic`` crosses drums and harmony over two bars around
a bass swap; ``drums_only`` (key clash) lets only the drums overlap while A's bass, other and
vocals leave before B's arrive (a Mosaikbox-style removal of clashing stems).
"""

from mixconsole.analysis.models import TrackAnalysis
from mixconsole.mixscript.models import (
    AutomationLane,
    AutomationPoint,
    Effect,
    StemTarget,
    TrackTarget,
)
from mixconsole.mixscript.models import Family as FamilyName
from mixconsole.plan import vocals
from mixconsole.plan.candidates import Candidate, PlanContext, effective_tempo
from mixconsole.score.heuristic import key_compatibility

STEM_FAMILIES = ("stem_handoff", "vocal_over_instrumental")
UNAVAILABLE = (
    "stems unavailable: install the 'stems' extra and run `mixconsole models fetch htdemucs`"
)
Point = tuple[float, float, str]


def _lane(track: str, stem: str, points: list[Point]) -> AutomationLane:
    cleaned: list[Point] = []
    for beat, value, curve in points:
        if cleaned and beat <= cleaned[-1][0] + 1e-9:
            cleaned[-1] = (cleaned[-1][0], value, cleaned[-1][2])
            continue
        cleaned.append((beat, value, curve))
    return AutomationLane(
        id=f"{track}_{stem}_gain",
        target=StemTarget(kind="stem", track=track, stem=stem),  # type: ignore[arg-type]
        parameter="gain",
        points=[AutomationPoint(beat=b, value=v, curve=c) for b, v, c in cleaned],  # type: ignore[arg-type]
    )


class StemFamily:
    version = "1"

    def __init__(self, name: FamilyName) -> None:
        self.name: FamilyName = name

    def unavailable(self, a: TrackAnalysis, b: TrackAnalysis) -> str | None:
        if a.stems is None or b.stems is None or not a.vocal_activity or not b.vocal_activity:
            return UNAVAILABLE
        return None

    def candidates(self, a: TrackAnalysis, b: TrackAnalysis, ctx: PlanContext) -> list[Candidate]:
        lengths = (4, 8, 16) if self.name == "stem_handoff" else (8, 16)
        variant = (
            ("drums_only" if key_compatibility(a, b) < 0.5 else "classic")
            if self.name == "stem_handoff"
            else "acapella"
        )
        found: list[Candidate] = []
        for exit_seconds in ctx.exits:
            for entry_seconds in ctx.entries:
                for bars in lengths:
                    candidate = Candidate(
                        "pending",
                        self.name,
                        exit_seconds,
                        entry_seconds,
                        bars,
                        ctx.bpm,
                        ctx.strategy,
                        beats_per_bar=a.meter,
                        variant=variant,
                    )
                    if ctx.strategy == "no_sync":
                        candidate.veto = "stem transitions need a beatmatchable pair"
                    else:
                        candidate.params, candidate.veto = self.schedule(a, b, candidate)
                    found.append(candidate)
        return found

    def applicable(self, a: TrackAnalysis, b: TrackAnalysis, candidate: Candidate) -> bool | str:
        return candidate.veto or True

    def schedule(
        self, a: TrackAnalysis, b: TrackAnalysis, c: Candidate
    ) -> tuple[dict[str, float], str | None]:
        """Gain-lane beats (transition-relative) or the reason the candidate is impossible."""
        meter = c.beats_per_bar
        bpm = c.bpm or 120.0
        beats = float(c.length_bars * meter)
        duration = beats * 60 / bpm
        scale = effective_tempo(b, bpm) / bpm  # B source seconds -> transition seconds
        source = duration / scale
        wa, wb = vocals.window_of(a, "exit"), vocals.window_of(b, "entry")
        va, vb = a.vocal_activity, b.vocal_activity
        if wa is None or wb is None or va is None or vb is None:
            return {}, UNAVAILABLE
        if c.exit_seconds < wa[0] - 1e-3 or c.exit_seconds + duration > wa[1] + 0.25:
            return {}, "exit transition lies outside the separated exit window"
        if c.entry_seconds < wb[0] - 1e-3 or c.entry_seconds + source > wb[1] + 0.25:
            return {}, "entry transition lies outside the separated entry window"
        if not vocals.in_stem_region(a, c.exit_seconds, c.exit_seconds + duration):
            return {}, "outgoing vocal activity is not stem-derived here"
        if not vocals.in_stem_region(b, c.entry_seconds, c.entry_seconds + source):
            return {}, "incoming vocal activity is not stem-derived here"
        beat_s = 60 / bpm

        def b_beat(seconds: float) -> float:
            return (seconds - c.entry_seconds) * scale / beat_s

        params: dict[str, float] = {}
        if self.name == "vocal_over_instrumental":
            if key_compatibility(a, b) < 1.0:
                return {}, "keys are not compatible (needs same key, Camelot +-1 or relative)"
            if (
                vocals.covered(vb.spans, c.entry_seconds, c.entry_seconds + source + 2 * beat_s)
                > 0.05
            ):
                return {}, "incoming track has vocals in its intro"
            if vocals.covered(va.spans, c.exit_seconds, c.exit_seconds + duration / 2) < beat_s:
                return {}, "no outgoing vocal to carry over the instrumental"
            gap = vocals.next_gap_time(
                va, c.exit_seconds + duration / 2, c.exit_seconds + duration - 2 * beat_s
            )
            if gap is None:
                return {}, "outgoing vocal has no lyric gap to exit at"
            out = (gap - c.exit_seconds) / beat_s + 0.1
            params = {
                "swap_beat": float(meter),
                "vocal_out_beat": out,
                "vocal_in_beat": min(beats - 0.25, out + 0.75),
            }
            return params, None
        gap = vocals.next_gap_time(va, c.exit_seconds, c.exit_seconds + 0.75 * duration)
        if gap is None:
            return {}, "outgoing vocal has no lyric gap to exit at"
        out = min(beats - 1.0, (gap - c.exit_seconds) / beat_s + 0.1)
        earliest, latest = out + 0.5, beats - 0.25
        enter = latest
        late_start = c.entry_seconds + earliest * beat_s / scale
        late_end = c.entry_seconds + beats * beat_s / scale
        onsets = [
            b_beat(s.start)
            for s in vb.spans
            if earliest <= b_beat(s.start) <= latest and s.start > c.entry_seconds
        ]
        if onsets:
            enter = max(earliest, min(onsets) - 0.25)
        elif vocals.covered(vb.spans, late_start, late_end) > 0:
            return {}, "incoming vocal phrase straddles the handoff with no onset to enter at"
        swap = max(float(meter), round(beats / 2 / meter) * float(meter))
        params = {
            "swap_beat": min(swap, beats - meter),
            "vocal_out_beat": out,
            "vocal_in_beat": enter,
        }
        return params, None

    def automation(self, candidate: Candidate) -> tuple[list[AutomationLane], list[Effect]]:
        p = candidate.params
        beats = float(candidate.length_bars * candidate.beats_per_bar)
        meter = float(candidate.beats_per_bar)
        swap, out, enter = p["swap_beat"], p["vocal_out_beat"], p["vocal_in_beat"]
        x0, x1 = max(0.0, swap - meter), min(beats, swap + meter)
        acapella = self.name == "vocal_over_instrumental"
        a_name, b_name = "deck_a", "deck_b"
        if acapella:
            x0, x1 = 0.0, min(beats, 2 * meter)
        lanes: list[AutomationLane] = []

        def hold_then_cut(start: float, end: float) -> tuple[list[Point], list[Point]]:
            """(A, B) lanes: A holds until ``start`` then equal-power to 0; B mirrors."""
            return (
                [(0, 1, "linear"), (start, 1, "equal_power"), (end, 0, "linear")],
                [(0, 0, "linear"), (start, 0, "equal_power"), (end, 1, "linear")],
            )

        def swap_lane(at: float, fade: float) -> tuple[list[Point], list[Point]]:
            return (
                [(0, 1, "linear"), (max(0.001, at - fade), 1, "linear"), (at, 0, "linear")],
                [(0, 0, "linear"), (at, 0, "linear"), (at + fade, 1, "linear")],
            )

        drums_a, drums_b = hold_then_cut(x0, x1)
        lanes += [_lane(a_name, "drums", drums_a), _lane(b_name, "drums", drums_b)]
        bass_a, bass_b = swap_lane(swap, 0.125)
        lanes += [_lane(a_name, "bass", bass_a), _lane(b_name, "bass", bass_b)]
        if candidate.variant == "drums_only":
            other_a, other_b = swap_lane(swap, 0.25)
        else:
            other_a, other_b = hold_then_cut(x0, x1)
        lanes += [_lane(a_name, "other", other_a), _lane(b_name, "other", other_b)]
        vocals_a: list[Point] = [(0, 1, "linear"), (out, 1, "linear"), (out + 0.25, 0, "linear")]
        vocals_b: list[Point] = [
            (0, 0, "linear"),
            (enter, 0, "linear"),
            (enter + 0.25, 1, "linear"),
        ]
        lanes += [_lane(a_name, "vocals", vocals_a), _lane(b_name, "vocals", vocals_b)]
        effect = Effect(
            id="stem_plan",
            name="stem_plan",
            target=TrackTarget(kind="track", track=a_name),
            params={"variant": candidate.variant, **{k: round(v, 4) for k, v in p.items()}},
        )
        return lanes, [effect]
