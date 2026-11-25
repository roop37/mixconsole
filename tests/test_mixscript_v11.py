"""MixScript v1.1: stable ids, per-transition explanation/candidates, locks, play, extensions."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from mixconsole.mixscript import (
    LATEST_VERSION,
    MixScript,
    dumps_mixscript,
    load_mixscript,
    upgrade,
)
from mixconsole.mixscript.migrations import validate_locks

ROOT = Path(__file__).resolve().parents[1]
V1_FIXTURES = sorted((ROOT / "tests/fixtures").glob("v1-*.mixscript.json"))


@pytest.fixture
def latest():
    return json.loads((ROOT / "examples/trim-crossfade.mixscript.json").read_text())


@pytest.mark.parametrize("path", V1_FIXTURES, ids=lambda p: p.name)
def test_v1_still_loads_and_upgrades_deterministically(path):
    data = json.loads(path.read_text())
    assert load_mixscript(path).version == "mixscript/v1"
    first, second = upgrade(data), upgrade(data)
    assert first == second
    assert first["version"] == LATEST_VERSION
    assert upgrade(first) == first  # idempotent
    assert data["version"] == "mixscript/v1"  # input untouched
    script = load_mixscript(path, upgrade_to_latest=True)
    ids = [t.id for t in script.transitions]
    ids += [lane.id for t in script.transitions for lane in t.automation]
    assert all(ids)
    assert len(ids) == len(set(ids))


def test_upgrade_preserves_existing_ids_and_avoids_collisions():
    data = json.loads(V1_FIXTURES[0].read_text())
    data["transitions"][0]["id"] = "transition_0_automation_0"
    upgraded = upgrade(data)
    lane_ids = [lane["id"] for lane in upgraded["transitions"][0]["automation"]]
    assert upgraded["transitions"][0]["id"] == "transition_0_automation_0"
    assert "transition_0_automation_0" not in lane_ids


@pytest.mark.parametrize("path", sorted((ROOT / "examples").glob("*.json")), ids=lambda p: p.name)
def test_canonical_dump_round_trips_and_is_stable(path):
    script = load_mixscript(path)
    text = dumps_mixscript(script)
    again = MixScript.model_validate_json(text)
    assert again == script
    assert dumps_mixscript(again) == text
    assert text == path.read_text()  # committed examples are canonical


def test_v11_requires_ids(latest):
    del latest["transitions"][0]["id"]
    with pytest.raises(ValidationError, match="require ids"):
        MixScript.model_validate(latest)


def test_ids_unique_across_tracks_transitions_and_lanes(latest):
    latest["transitions"][0]["id"] = next(iter(latest["tracks"]))
    with pytest.raises(ValidationError, match="unique"):
        MixScript.model_validate(latest)


def test_locks_and_lock_enforcement(latest):
    transition = latest["transitions"][0]
    lane_id = transition["automation"][0]["id"]
    transition["locks"] = ["exit", lane_id]
    script = MixScript.model_validate(latest)
    before = script.transitions[0]
    assert json.loads(dumps_mixscript(script))["transitions"][0]["locks"] == sorted(
        ["exit", lane_id]
    )
    moved = before.model_copy(update={"exit": before.entry})
    with pytest.raises(ValueError, match="locked value changed: exit"):
        validate_locks(before, moved)
    validate_locks(before, before.model_copy(update={"length_bars": before.length_bars + 1}))
    bad = deepcopy(latest)
    bad["transitions"][0]["locks"] = ["not_a_field"]
    with pytest.raises(ValidationError, match="locks"):
        MixScript.model_validate(bad)


def test_per_transition_explanation_and_candidates(latest):
    transition = latest["transitions"][0]
    transition["explanation"] = {
        "chosen_because": "phrase-aligned, no vocal overlap",
        "score_breakdown": {"phrase": 1.0, "energy": 0.8},
    }
    transition["candidates"] = [
        {
            "id": "cand_a",
            "family": "trim_crossfade",
            "exit": transition["exit"],
            "entry": transition["entry"],
            "length_bars": 2,
            "score": 0.91,
            "preview_artifact": "previews/cand_a.opus",
        }
    ]
    script = MixScript.model_validate(latest)
    assert script.transitions[0].candidates[0].score == 0.91
    assert MixScript.model_validate_json(dumps_mixscript(script)) == script


def test_extensions_are_namespaced_and_preserved(latest):
    latest["extensions"] = {"ui.colors": {"deck_a": "#ff0055"}}
    script = MixScript.model_validate(latest)
    assert json.loads(dumps_mixscript(script))["extensions"] == latest["extensions"]
    latest["extensions"] = {"colors": 1}
    with pytest.raises(ValidationError, match="namespaced"):
        MixScript.model_validate(latest)


def test_play_region_round_trip_and_cue_bounds(latest):
    track_id = latest["transitions"][0]["from_track"]
    exit_seconds = latest["transitions"][0]["exit"]["seconds"]
    latest["tracks"][track_id]["play"] = {"in_seconds": 1.0, "out_seconds": exit_seconds + 1}
    script = MixScript.model_validate(latest)
    assert MixScript.model_validate_json(dumps_mixscript(script)) == script
    latest["tracks"][track_id]["play"] = {"in_seconds": 1.0, "out_seconds": exit_seconds - 1}
    with pytest.raises(ValidationError, match="play region"):
        MixScript.model_validate(latest)
