"""Structural and semantic contract regressions."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from mixconsole.mixscript import MixScript, load_mixscript, schema_json

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def example():
    return json.loads((ROOT / "examples/trim-crossfade.mixscript.json").read_text())


@pytest.mark.parametrize("path", sorted((ROOT / "examples").glob("*.json")))
def test_examples_validate_and_round_trip(path):
    script = load_mixscript(path)
    assert MixScript.model_validate_json(script.model_dump_json()) == script
    assert script.version == "mixscript/v1.1"


@pytest.mark.parametrize("version", ["mixscript/v1", "mixscript/v1.1"])
def test_committed_schema_matches(version):
    name = "mixscript-" + version.split("/")[1] + ".json"
    assert (ROOT / "schemas" / name).read_text() == schema_json(version)


@pytest.mark.parametrize(
    ("field", "value"),
    [("version", "mixscript/v2"), ("unknown", 42), ("tracks", {}), ("provenance", {})],
)
def test_invalid_top_level(example, field, value):
    example[field] = value
    with pytest.raises(ValidationError):
        MixScript.model_validate(example)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("content_sha256", "bad"),
        ("duration", -1),
        ("duration", float("nan")),
        ("sample_rate", 0),
        ("sample_rate", True),
    ],
)
def test_invalid_track(example, field, value):
    example["tracks"]["deck_a"][field] = value
    with pytest.raises(ValidationError):
        MixScript.model_validate(example)


@pytest.mark.parametrize(
    "case",
    [
        "reference",
        "self",
        "cue",
        "tempo",
        "target",
        "duplicate",
        "order",
        "nan",
        "curve",
        "filter",
        "key",
    ],
)
def test_invalid_transition(example, case):
    transition = example["transitions"][0]
    lane = transition["automation"][0]
    match case:
        case "reference":
            del example["tracks"]["deck_b"]
        case "self":
            transition["to_track"] = "deck_a"
        case "cue":
            transition["exit"]["seconds"] = 65
        case "tempo":
            transition["tempo"]["tempo_map"].append({"beat": 0, "bpm": 130})
        case "target":
            lane["target"]["track"] = "missing"
        case "duplicate":
            transition["automation"].append(deepcopy(lane))
        case "order":
            lane["points"].reverse()
        case "nan":
            lane["points"][0]["value"] = float("nan")
        case "curve":
            lane["points"][0]["curve"] = "exponential"
        case "filter":
            lane["parameter"] = "hpf"
        case "key":
            transition["key"]["semitones"] = 1
    with pytest.raises(ValidationError):
        MixScript.model_validate(example)


@settings(max_examples=20, derandomize=True)
@given(seed=st.integers(min_value=0, max_value=2**63 - 1))
def test_seed_round_trip(seed):
    script = load_mixscript(ROOT / "examples/trim-crossfade.mixscript.json")
    script.provenance.seed = seed
    assert MixScript.model_validate_json(script.model_dump_json()).provenance.seed == seed
