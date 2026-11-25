"""Interval queries over ``VocalActivity`` used by the stem families and the scorer."""

from mixconsole.analysis.models import Span, TrackAnalysis, VocalActivity


def covered(spans: list[Span], start: float, end: float) -> float:
    """Seconds of [start, end) covered by ``spans``."""
    return sum(max(0.0, min(s.end, end) - max(s.start, start)) for s in spans)


def active_at(activity: VocalActivity | None, seconds: float) -> bool:
    return activity is not None and any(s.start <= seconds < s.end for s in activity.spans)


def overlap_seconds(
    a: VocalActivity, b: VocalActivity, a_start: float, b_start: float, length: float, scale: float
) -> float:
    """Seconds in [0, length) of transition time where A and B vocals are both active.

    ``scale`` converts B source seconds to transition seconds (effective_bpm / bpm).
    """
    a_spans = [
        (max(s.start - a_start, 0.0), min(s.end - a_start, length))
        for s in a.spans
        if s.end > a_start and s.start < a_start + length
    ]
    total = 0.0
    for s in b.spans:
        lo, hi = (s.start - b_start) * scale, (s.end - b_start) * scale
        lo, hi = max(lo, 0.0), min(hi, length)
        if hi <= lo:
            continue
        total += sum(max(0.0, min(hi, y) - max(lo, x)) for x, y in a_spans)
    return total


def next_gap_time(activity: VocalActivity, start: float, limit: float) -> float | None:
    """Earliest moment in [start, limit] at which the vocal is silent for a lyric gap.

    Returns ``start`` when no vocal is active there, otherwise the start of the first
    gap (>= 300 ms) that begins at or before ``limit``; ``None`` when there is none.
    """
    if not any(s.start <= start < s.end for s in activity.spans):
        return start
    for gap in activity.gaps:
        if gap.end > start and gap.start <= limit:
            return max(gap.start, start)
    return None


def in_stem_region(analysis: TrackAnalysis, start: float, end: float) -> bool:
    """True when stems (and hence trustworthy vocal data) cover [start, end].

    The end may overrun the window by up to 250 ms (fade tails, edge silence).
    """
    activity = analysis.vocal_activity
    if activity is None:
        return False
    return any(r.start <= start + 1e-3 and end <= r.end + 0.25 for r in activity.stem_regions)


def window_of(analysis: TrackAnalysis, role: str) -> tuple[float, float] | None:
    if analysis.stems is None:
        return None
    for window in analysis.stems.windows:
        if window.role == role:
            return window.start, window.end
    return None
