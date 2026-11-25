"""Cheap bounded [0, 1] features for M2 ranking."""

import math
from functools import lru_cache
from importlib.resources import files

import yaml

from mixconsole.analysis.models import TrackAnalysis
from mixconsole.plan import vocals
from mixconsole.plan.candidates import Candidate, effective_tempo, has_beat_grid

SCORER_VERSION = "heuristic@5"


@lru_cache(maxsize=1)
def weights() -> dict[str, dict[str, float]]:
    source = files("mixconsole.score").joinpath("weights.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(source)  # type: ignore[no-any-return]


def total(features: dict[str, float], style: str) -> float:
    return sum(features[name] * weight for name, weight in weights()[style].items())


_PRIOR = {
    "auto": {
        "beatmatch_blend": 1.0,
        "trim_crossfade": 0.55,
        "cut_on_downbeat": 0.76,
        "echo_out": 0.75,
        "filter_sweep": 0.65,
        "gapless": 0.6,
        "stem_handoff": 0.9,
        "vocal_over_instrumental": 0.8,
    },
    "smooth": {
        "trim_crossfade": 1.0,
        "cut_on_downbeat": 0.8,
        "echo_out": 0.65,
        "beatmatch_blend": 0.50,
        "filter_sweep": 0.45,
        "gapless": 0.6,
        "stem_handoff": 0.5,
        "vocal_over_instrumental": 0.4,
    },
    "club": {
        "beatmatch_blend": 1.0,
        "filter_sweep": 0.8,
        "echo_out": 0.55,
        "trim_crossfade": 0.50,
        "cut_on_downbeat": 0.35,
        "gapless": 0.3,
        "stem_handoff": 1.0,
        "vocal_over_instrumental": 0.85,
    },
}


def _energy(analysis: TrackAnalysis, seconds: float) -> float:
    if not analysis.bars or "bar_energy" not in analysis.arrays:
        return 0.5
    index = min(range(len(analysis.bars)), key=lambda i: abs(analysis.bars[i].start - seconds))
    values = analysis.arrays["bar_energy"]
    return float(values[min(index, len(values) - 1), 0])


def key_compatibility(a: TrackAnalysis, b: TrackAnalysis) -> float:
    """1.0 for the same key, Camelot +-1 or relative major/minor; decays with wheel distance."""
    na, nb = a.key.camelot, b.key.camelot
    distance = min((int(na[:-1]) - int(nb[:-1])) % 12, (int(nb[:-1]) - int(na[:-1])) % 12)
    return (
        1.0
        if (
            na == nb
            or (na[-1] == nb[-1] and distance == 1)
            or (na[:-1] == nb[:-1] and na[-1] != nb[-1])
        )
        else max(0.0, 0.7 - 0.17 * distance)
    )


def key_reliability(a: TrackAnalysis, b: TrackAnalysis) -> float:
    """How far the weaker key estimate is above chance, in [0, 1].

    ``Key.confidence`` is a probability over 24 keys (chance 1/24, a clear synthetic key
    ~0.28, real tracks measured 0.06-0.15), so it is rescaled between chance and 0.25.
    Real-music key accuracy is unverified; the clash rule is weighted by this value.
    """
    weakest = min(a.key.confidence, b.key.confidence)
    return min(1.0, max(0.0, (weakest - 1 / 24) / (0.25 - 1 / 24)))


def vocal_safety(c: Candidate, a: TrackAnalysis, b: TrackAnalysis) -> float:
    """1 minus the predicted lead-vocal collision, shrunk by vocal-data confidence.

    Overlapping families lose points for A-vocal/B-vocal coexistence; a hard cut loses
    points when it lands mid-vocal. Stem families schedule vocals apart (1.0).
    """
    va, vb = a.vocal_activity, b.vocal_activity
    if va is None or vb is None or c.family in ("stem_handoff", "vocal_over_instrumental"):
        return 1.0
    confidence = min(va.confidence, vb.confidence)
    if c.length_bars == 0 or c.duration <= 0:
        mid = 0.5 if vocals.active_at(va, c.exit_seconds) else 0.0
        return 1.0 - mid * va.confidence
    scale = effective_tempo(b, c.bpm) / c.bpm if c.family == "beatmatch_blend" and c.bpm else 1.0
    seconds = vocals.overlap_seconds(
        va, vb, c.exit_seconds, c.entry_seconds, c.duration, scale or 1.0
    )
    collision = min(1.0, 1.5 * seconds / c.duration)
    # The spectral heuristic over-detects vocals (most bars of a real song), so without
    # stem-grade data in the window the penalty is only mild and never favours stem families.
    stem_grade = vocals.in_stem_region(
        a, c.exit_seconds, c.exit_seconds + c.duration
    ) and vocals.in_stem_region(b, c.entry_seconds, c.entry_seconds + c.duration)
    return 1.0 - collision * confidence * (1.0 if stem_grade else 0.5)


def score(c: Candidate, a: TrackAnalysis, b: TrackAnalysis, style: str) -> dict[str, float]:
    """All feature values are higher-is-better and clipped to [0,1]."""
    key = key_compatibility(a, b)
    energy_a, energy_b = _energy(a, c.exit_seconds), _energy(b, c.entry_seconds)
    continuity = math.exp(-abs(math.log((energy_a + 1e-6) / (energy_b + 1e-6))) / 3)
    stretch = (
        1.0
        if c.tempo_strategy in ("none", "no_sync") or not a.global_bpm or not b.global_bpm
        else max(0.0, 1 - abs(a.global_bpm - b.global_bpm) / a.global_bpm / 0.08)
    )
    desired = 12 if style == "club" else 2 if style == "smooth" else 8
    length = math.exp(-abs(c.length_bars - desired) / max(desired, 1))
    wasted = max(
        0.0,
        1
        - ((a.duration - c.exit_seconds - c.duration) + c.entry_seconds)
        / (a.duration + b.duration),
    )
    la, lb = a.loudness.integrated_lufs, b.loudness.integrated_lufs
    loudness = max(0.0, 1 - abs(la - lb) / 12) if la is not None and lb is not None else 0.5
    section = max(0.0, 1 - energy_a / (energy_a + 1))
    incompatible_tempo = (
        a.global_bpm is None
        or b.global_bpm is None
        or not has_beat_grid(a)
        or not has_beat_grid(b)
        or min(abs(a.global_bpm - b.global_bpm * scale) / a.global_bpm for scale in (0.5, 1.0, 2.0))
        > 0.08
    )
    family_prior = (
        (1.0 if c.family == "echo_out" else 0.95 if c.family == "cut_on_downbeat" else 0.35)
        if incompatible_tempo
        else _PRIOR[style].get(c.family, 0.5)
    )
    clash = key < 0.2
    clash_weight = key_reliability(a, b) if clash else 0.0
    forced = (
        1.0
        if c.family in ("echo_out", "cut_on_downbeat")
        or (c.family == "stem_handoff" and c.variant == "drums_only")
        else 0.25
        if c.family in ("beatmatch_blend", "stem_handoff", "vocal_over_instrumental")
        else family_prior
    )
    if a.edges.hard_ending:
        family_prior = forced
    elif clash:
        # The key-clash rule is weighted by key confidence (real-music key accuracy is unverified).
        family_prior = clash_weight * forced + (1 - clash_weight) * family_prior
    return {
        "phrase_alignment": 1.0,
        "key_compatibility": key,
        "energy_continuity": continuity,
        "stretch_cost": stretch,
        "section_fit": section,
        "length_fit": length,
        "wasted_audio": wasted,
        "loudness_gap": loudness,
        "vocal_safety": vocal_safety(c, a, b),
        "family_prior": family_prior,
    }
