"""Cheap bounded [0, 1] features for M2 ranking."""

import math
from functools import lru_cache
from importlib.resources import files

import yaml

from mixconsole.analysis.models import TrackAnalysis
from mixconsole.plan.candidates import Candidate, has_beat_grid

SCORER_VERSION = "heuristic@3"


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
    },
    "smooth": {
        "trim_crossfade": 1.0,
        "cut_on_downbeat": 0.8,
        "echo_out": 0.65,
        "beatmatch_blend": 0.50,
        "filter_sweep": 0.45,
        "gapless": 0.6,
    },
    "club": {
        "beatmatch_blend": 1.0,
        "filter_sweep": 0.8,
        "echo_out": 0.55,
        "trim_crossfade": 0.50,
        "cut_on_downbeat": 0.35,
        "gapless": 0.3,
    },
}


def _energy(analysis: TrackAnalysis, seconds: float) -> float:
    if not analysis.bars or "bar_energy" not in analysis.arrays:
        return 0.5
    index = min(range(len(analysis.bars)), key=lambda i: abs(analysis.bars[i].start - seconds))
    values = analysis.arrays["bar_energy"]
    return float(values[min(index, len(values) - 1), 0])


def score(c: Candidate, a: TrackAnalysis, b: TrackAnalysis, style: str) -> dict[str, float]:
    """All feature values are higher-is-better and clipped to [0,1]."""
    na, nb = a.key.camelot, b.key.camelot
    distance = min((int(na[:-1]) - int(nb[:-1])) % 12, (int(nb[:-1]) - int(na[:-1])) % 12)
    key = (
        1.0
        if (
            na == nb
            or (na[-1] == nb[-1] and distance == 1)
            or (na[:-1] == nb[:-1] and na[-1] != nb[-1])
        )
        else max(0.0, 0.7 - 0.17 * distance)
    )
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
    if a.edges.hard_ending or key < 0.2:
        family_prior = (
            1.0
            if c.family in ("echo_out", "cut_on_downbeat")
            else 0.25
            if c.family == "beatmatch_blend"
            else family_prior
        )
    return {
        "phrase_alignment": 1.0,
        "key_compatibility": key,
        "energy_continuity": continuity,
        "stretch_cost": stretch,
        "section_fit": section,
        "length_fit": length,
        "wasted_audio": wasted,
        "loudness_gap": loudness,
        "family_prior": family_prior,
    }
