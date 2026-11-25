"""Dataset evaluation uses synthetic local fixtures, never downloaded music."""

import json

import pytest
from typer.testing import CliRunner

from mixconsole.bench.datasets import read_annotation, run_dataset
from mixconsole.cli import app
from mixconsole.io import write_audio
from mixconsole.testing.synth import generate_track


def test_dataset_rhythm_and_missing_audio(tmp_path):
    labels = tmp_path / "annotations"
    labels.mkdir()
    audio, truth = generate_track(bars=4, bpm=120)
    write_audio(tmp_path / "track.wav", audio)
    text = "\n".join(f"{time} {i % 4 + 1}" for i, time in enumerate(truth["beat_times"]))
    (labels / "track.beats").write_text(text)
    (labels / "missing.beats").write_text(text)
    result = run_dataset("ballroom", tmp_path)
    assert result.metrics["beat_f"] == 1
    assert result.metrics["tempo_acc1"] == 1
    assert result.metrics["evaluated"] == 1
    assert result.metrics["excluded"] == 1
    assert len(result.parameters["annotations_sha256"]) == 64
    assert "missing.beats" in result.notes[-1]


@pytest.mark.parametrize(
    ("suffix", "value", "expected"),
    [("key", "Db minor", (1, "minor")), ("key", "C#:maj", (1, "major")), ("bpm", "120", 120)],
)
def test_native_annotation_formats(tmp_path, suffix, value, expected):
    path = tmp_path / f"123.LOFI.{suffix}"
    path.write_text(value)
    annotation = read_annotation(path)
    actual = (annotation.tonic, annotation.mode) if suffix == "key" else annotation.bpm
    assert actual == expected


@pytest.mark.parametrize(
    ("suffix", "value"), [("bpm", "0"), ("bpm", "nan"), ("beats", "2 1\n1 2"), ("beats", "0 0")]
)
def test_invalid_annotations(tmp_path, suffix, value):
    path = tmp_path / f"x.{suffix}"
    path.write_text(value)
    with pytest.raises(ValueError, match=r"tempo|beat"):
        read_annotation(path)


def test_dataset_cli_instructions_and_evaluation(tmp_path):
    runner = CliRunner()
    missing = runner.invoke(
        app, ["bench", "dataset", "giantsteps_tempo", "--audio-dir", str(tmp_path / "absent")]
    )
    assert missing.exit_code == 0
    assert "Download annotations yourself" in missing.output
    labels = tmp_path / "annotations"
    labels.mkdir()
    (labels / "123.LOFI.bpm").write_text("120")
    audio, _ = generate_track(bars=4)
    write_audio(tmp_path / "123.LOFI.wav", audio)
    out = tmp_path / "results"
    result = runner.invoke(
        app,
        ["bench", "dataset", "giantsteps_tempo", "--audio-dir", str(tmp_path), "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(next(out.glob("*.json")).read_text())
    assert data["metrics"]["tempo_acc1"] == 1
    assert "giantsteps_tempo" in (out / "LATEST.md").read_text()
    write_audio(tmp_path / "123.LOFI.flac", audio)
    with pytest.raises(ValueError, match="no evaluable"):
        run_dataset("giantsteps_tempo", tmp_path)
    unknown = runner.invoke(app, ["bench", "dataset", "unknown", "--audio-dir", str(tmp_path)])
    assert unknown.exit_code == 1
