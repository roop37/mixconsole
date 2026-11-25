"""Hard, explainable proposal constraints."""

from mixconsole.analysis.models import TrackAnalysis
from mixconsole.config import Settings
from mixconsole.plan.candidates import Candidate, has_beat_grid


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
    return None
