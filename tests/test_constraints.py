"""Every hard planning constraint returns an explainable reason (or None when valid)."""

import numpy as np
import pytest

from mixconsole.analysis import analyze
from mixconsole.config import Settings
from mixconsole.io import write_audio
from mixconsole.plan.candidates import Candidate
from mixconsole.plan.constraints import rejection_reason
from mixconsole.testing.synth import generate_track


@pytest.fixture(scope="module")
def tracks(tmp_path_factory):
    folder = tmp_path_factory.mktemp("constraints")
    beat, _ = generate_track(bpm=120, bars=16, seed=1)
    pads, _ = generate_track(bpm=120, bars=16, percussion="none", seed=2)
    a = analyze(write_audio(folder / "a.wav", beat), use_cache=False)
    silent = analyze(
        write_audio(folder / "s.wav", np.zeros((44100 * 8, 2), np.float32)), use_cache=False
    )
    p = analyze(write_audio(folder / "p.wav", pads), use_cache=False)
    return a, silent, p


def cand(family="beatmatch_blend", exit_s=20.0, entry_s=0.0, bars=2, strategy="none"):
    return Candidate("c1", family, exit_s, entry_s, bars, 120.0, strategy)


@pytest.mark.parametrize(
    ("candidate", "locks", "reason"),
    [
        (cand(), {"family": "echo_out"}, "locked family"),
        (cand(), {"exit": 10.0}, "locked exit cue"),
        (cand(), {"entry": 4.0}, "locked entry cue"),
        (cand(), {"length_bars": 8}, "locked transition length"),
        (cand(exit_s=-1), {}, "cue outside track"),
        (cand(exit_s=31.5, bars=4), {}, "transition does not fit both tracks"),
        (cand(strategy="no_sync"), {}, "tempo difference exceeds stretch limit"),
        (cand(family="filter_sweep", bars=0), {}, "blend needs a positive length"),
        (cand(), {"exit": 20.0, "family": "beatmatch_blend"}, None),
    ],
)
def test_rejection_reasons(tracks, candidate, locks, reason):
    a, _, _ = tracks
    got = rejection_reason(a, a, candidate, Settings(), locks)
    assert (got is None) if reason is None else (got is not None and got.startswith(reason))


def test_beatless_track_requires_non_beatmatched(tracks):
    a, silent, _ = tracks
    got = rejection_reason(a, silent, cand(exit_s=20.0, bars=1), Settings(), {})
    assert got is not None
    assert "beat" in got
    assert (
        rejection_reason(a, silent, cand(family="cut_on_downbeat", bars=0), Settings(), {}) is None
    )
