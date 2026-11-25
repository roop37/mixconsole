"""R2/M3 coverage: every render family path, effects, stretch edge cases and constraints.

Assertions are on audio properties (length, finiteness, level, ceiling), not just "runs".
"""

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from mixconsole.io import SAMPLE_RATE
from mixconsole.mixscript import MixScript
from mixconsole.render.graph import RenderInspection, render_transition
from mixconsole.render.limiter import true_peak_dbtp
from mixconsole.render.stretch import ramp_back, stretch, stretch_piecewise

ROOT = Path(__file__).resolve().parents[1]
BAR = 4 * 60 / 120 * SAMPLE_RATE  # 2 s at 120 BPM


def tone(seconds: float, hz: float, level: float = 0.25) -> np.ndarray:
    t = np.arange(round(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    mono = (level * np.sin(2 * np.pi * hz * t)).astype(np.float32)
    return np.stack((mono, mono), axis=1)


@pytest.fixture(scope="module")
def decks():
    return tone(64, 110), tone(64, 165)


def script_for(family: str, *, length_bars: int = 2, effects=(), strategy: str = "none"):
    data = json.loads((ROOT / "examples/trim-crossfade.mixscript.json").read_text())
    t = data["transitions"][0]
    t["family"] = family
    t["length_bars"] = length_bars
    t["automation"] = []
    t["effects"] = [
        {
            "id": f"fx{i}",
            "name": name,
            "target": {"kind": "track", "track": track},
            "params": params,
        }
        for i, (name, track, params) in enumerate(effects)
    ]
    t["tempo"]["strategy"] = strategy
    return MixScript.model_validate(deepcopy(data))


def check(out: np.ndarray, expected_len: int) -> None:
    assert out.dtype == np.float32
    assert out.shape[1] == 2
    assert np.isfinite(out).all()
    assert abs(len(out) - expected_len) <= 2
    assert true_peak_dbtp(out) <= -0.99


@pytest.mark.parametrize(
    ("family", "effects"),
    [
        ("trim_crossfade", ()),
        ("filter_sweep", [("filter_sweep", "deck_a", {"start_hz": 60.0, "end_hz": 6000.0})]),
        ("echo_out", [("echo", "deck_a", {"tail_beats": 2, "feedback": 0.5})]),
        ("beatmatch_blend", [("bass_swap", "deck_a", {"beat": 4.0})]),
        (
            "trim_crossfade",
            [("gain_match", "deck_b", {"db": -3.0}), ("seam_gain", "deck_a", {"db": 1.5})],
        ),
    ],
)
def test_family_paths_render_full_length(decks, family, effects):
    a, b = decks
    inspection = RenderInspection()
    out = render_transition(a, b, script_for(family, effects=effects), inspection=inspection)
    # A until exit (60 s) + 2-bar overlap + rest of B after the consumed overlap.
    check(out, round(60 * SAMPLE_RATE) + len(b))
    assert inspection.contribution_a is not None
    assert inspection.contribution_b is not None
    seam = slice(round(60 * SAMPLE_RATE), round(60 * SAMPLE_RATE + 2 * BAR))
    assert float(np.sqrt(np.mean(out[seam] ** 2))) > 0.02  # no dropout in the overlap


def test_beatmatch_bass_swap_hands_over_lows(decks):
    a, b = decks
    inspection = RenderInspection()
    render_transition(
        a,
        b,
        script_for("beatmatch_blend", effects=[("bass_swap", "deck_a", {"beat": 4.0})]),
        inspection=inspection,
    )
    ca, cb = inspection.contribution_a, inspection.contribution_b
    assert ca is not None
    assert cb is not None
    half = len(ca) // 2
    # Deck A's lows are present before the swap, deck B's only after it.
    assert np.abs(ca[: half - 100]).mean() > np.abs(ca[half + 100 :]).mean()
    assert np.abs(cb[half + 100 :]).mean() > np.abs(cb[: half - 100]).mean()


def test_cut_has_no_overlap(decks):
    a, b = decks
    out = render_transition(a, b, script_for("cut_on_downbeat", length_bars=0))
    check(out, round(60 * SAMPLE_RATE) + len(b))


def test_correlated_signals_do_not_gain_3db(decks):
    a, _ = decks
    out = render_transition(a, a.copy(), script_for("trim_crossfade"))
    seam = out[round(60 * SAMPLE_RATE) : round(60 * SAMPLE_RATE + 2 * BAR)]
    # Linear crossfade of identical signals keeps level (equal-power would add ~3 dB).
    level = 20 * np.log10(np.sqrt(np.mean(seam**2)) / np.sqrt(np.mean(a[:SAMPLE_RATE] ** 2)))
    assert abs(level) < 1.0


def test_stretch_edge_cases():
    audio = tone(1, 220)
    assert stretch(audio, 0).shape == (0, 2)
    assert np.array_equal(stretch(audio, len(audio)), audio)
    assert not stretch(np.empty((0, 2), np.float32), 100).any()
    longer = stretch(audio, round(len(audio) * 1.05))
    assert len(longer) == round(len(audio) * 1.05)
    assert np.isfinite(longer).all()


def test_stretch_piecewise_validates_points():
    audio = tone(2, 220)
    assert np.array_equal(stretch_piecewise(audio, [[0, 0]]), audio)
    warped = stretch_piecewise(audio, [[0, 0], [SAMPLE_RATE, 22000], [2 * SAMPLE_RATE, 46000]])
    assert len(warped) == 46000
    with pytest.raises(ValueError, match="increase"):
        stretch_piecewise(audio, [[0, 0], [0, 100]])
    with pytest.raises(ValueError, match="exceeds"):
        stretch_piecewise(audio, [[0, 0], [5 * SAMPLE_RATE, 5 * SAMPLE_RATE]])


def test_ramp_back():
    out, used = ramp_back(tone(8, 220), 124.0, 120.0, 0)
    assert len(out) == 0
    assert used == 0
    out, used = ramp_back(tone(8, 220), 124.0, 120.0, 1)
    assert used > 0
    assert np.isfinite(out).all()
    assert len(out) > 0
