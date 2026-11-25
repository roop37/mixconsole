"""Hard, explainable proposal constraints."""

from mixconsole.analysis.models import TrackAnalysis
from mixconsole.config import Settings
from mixconsole.plan import vocals
from mixconsole.plan.candidates import Candidate, effective_tempo, has_beat_grid


def rejection_reason(
    a: TrackAnalysis, b: TrackAnalysis, c: Candidate, settings: Settings, locks: dict[str, object]
) -> str | None:
    if "family" in locks and c.family != locks["family"]:
        return "locked family"
    if "exit" in locks and abs(c.exit_seconds - float(str(locks["exit"]))) > 0.001:
        return "locked exit cue"
    if "entry" in locks and abs(c.entry_seconds - float(str(locks["entry"]))) > 0.001:
        return "locked entry cue"
    if "length_bars" in locks and c.length_bars != locks["length_bars"]:
        return "locked transition length"
    if (
        c.exit_seconds < 0
        or c.exit_seconds > a.duration
        or c.entry_seconds < 0
        or c.entry_seconds > b.duration
    ):
        return "cue outside track"
    if c.duration > min(a.duration - c.exit_seconds, b.duration - c.entry_seconds) + 0.001:
        return "transition does not fit both tracks"
    if c.family == "beatmatch_blend" and c.tempo_strategy == "no_sync":
        return "tempo difference exceeds stretch limit or beat grid absent"
    if (not has_beat_grid(a) or not has_beat_grid(b)) and c.family not in (
        "trim_crossfade",
        "cut_on_downbeat",
        "echo_out",
    ):
        return "beatless track requires a non-beatmatched transition"
    if c.family in ("beatmatch_blend", "filter_sweep") and c.length_bars == 0:
        return "blend needs a positive length"
    return lead_vocal_clash(a, b, c, settings)


def lead_vocal_clash(
    a: TrackAnalysis, b: TrackAnalysis, c: Candidate, settings: Settings
) -> str | None:
    """Reject overlapping blends whose stem-derived vocals would collide for > 1 beat.

    Only stem-grade vocal data is trusted for a hard rule; the heuristic feeds the score.
    Stem families schedule vocals apart themselves.
    """
    va, vb = a.vocal_activity, b.vocal_activity
    if (
        c.length_bars == 0
        or c.family in ("stem_handoff", "vocal_over_instrumental", "gapless")
        or va is None
        or vb is None
        or va.confidence < 0.8
        or vb.confidence < 0.8
        or not c.bpm
    ):
        return None
    if not (
        vocals.in_stem_region(a, c.exit_seconds, c.exit_seconds + c.duration)
        and vocals.in_stem_region(b, c.entry_seconds, c.entry_seconds + c.duration)
    ):
        return None
    scale = effective_tempo(b, c.bpm) / c.bpm if c.family == "beatmatch_blend" else 1.0
    seconds = vocals.overlap_seconds(va, vb, c.exit_seconds, c.entry_seconds, c.duration, scale)
    limit = settings.max_vocal_overlap_beats * 60 / c.bpm
    if seconds > limit:
        return f"lead vocals would overlap for {seconds:.1f} s (limit {limit:.2f} s)"
    return None
