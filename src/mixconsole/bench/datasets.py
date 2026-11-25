"""Local-only public dataset hooks. No audio or annotations are downloaded."""

import hashlib
import itertools
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from mixconsole.analysis import analyze, registry
from mixconsole.bench.metrics import beat_f_measure, mirex_key_score, tempo_acc1, tempo_acc2
from mixconsole.bench.results import BenchResult, new_result

NAMES = ("ballroom", "gtzan_rhythm", "giantsteps_key", "giantsteps_tempo")
AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".au", ".ogg", ".aiff", ".m4a"}
SOURCES = {
    "ballroom": "https://github.com/CPJKU/BallroomAnnotations",
    "gtzan_rhythm": "https://github.com/CPJKU/beat_this_annotations/tree/main/gtzan",
    "giantsteps_key": "https://github.com/GiantSteps/giantsteps-key-dataset",
    "giantsteps_tempo": "https://github.com/GiantSteps/giantsteps-tempo-dataset",
}


class Annotation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    beats: list[float] = []
    downbeats: list[float] = []
    bpm: float | None = None
    tonic: int | None = None
    mode: Literal["major", "minor"] | None = None


def instructions(name: str, audio_dir: Path, annotations_dir: Path | None = None) -> str:
    if name not in NAMES:
        raise ValueError(f"unknown dataset {name}; choose {', '.join(NAMES)}")
    return (
        f"Dataset {name}: place your lawfully obtained audio under {audio_dir}.\n"
        f"Download annotations yourself from {SOURCES[name]} and place them under "
        f"{annotations_dir or audio_dir / 'annotations'} (or pass --annotations-dir).\n"
        "Keep original basenames, including .LOFI; nested audio directories are supported.\n"
        "Ballroom/GTZAN: two-column .beats (seconds, beat-in-bar; 1 = downbeat).\n"
        "GiantSteps: annotations/key/*.key or annotations_v2/tempo/*.bpm; "
        "pass that leaf directory to --annotations-dir.\n"
        "No downloads or redistribution are performed. See bench/datasets/*.yaml for terms."
    )


def read_annotation(path: Path) -> Annotation:
    text = path.read_text(encoding="utf-8").strip()
    if path.suffix == ".beats":
        rows = [line.split() for line in text.splitlines() if line.strip()]
        beats = [float(row[0]) for row in rows]
        if not beats or any(not math.isfinite(t) or t < 0 for t in beats):
            raise ValueError("invalid beat times")
        if any(b <= a for a, b in itertools.pairwise(beats)):
            raise ValueError("beat times must increase")
        positions = [int(row[1]) for row in rows]
        if any(position < 1 for position in positions):
            raise ValueError("beat positions must be positive")
        down = [t for t, pos in zip(beats, positions, strict=True) if pos == 1]
        gaps = [b - a for a, b in itertools.pairwise(beats)]
        return Annotation(
            beats=beats, downbeats=down, bpm=60 / statistics.median(gaps) if gaps else None
        )
    if path.suffix == ".bpm":
        bpm = float(text)
        if not math.isfinite(bpm) or bpm <= 0:
            raise ValueError("missing/invalid tempo (v2 zero labels are excluded)")
        return Annotation(bpm=bpm)
    note, mode = text.replace(":", " ").split()
    note = note.replace("♯", "#").replace("♭", "b")
    tonic = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[note[0].upper()]
    if len(note) > 1:
        tonic += {"#": 1, "b": -1}[note[1:]]
    modes: dict[str, Literal["major", "minor"]] = {
        "major": "major",
        "maj": "major",
        "minor": "minor",
        "min": "minor",
    }
    return Annotation(tonic=tonic % 12, mode=modes[mode.lower()])


def run_dataset(name: str, audio_dir: Path, annotations_dir: Path | None = None) -> BenchResult:
    """Macro-average over matched files; report exclusions and annotation fingerprint.

    Rhythm estimates are cropped to the annotated interval (±70 ms). Tempo is
    derived from median inter-beat time for Ballroom/GTZAN. Duplicate audio stems
    are rejected rather than selecting one arbitrarily. Missing files and malformed
    labels are counted and named in notes; absent audio never becomes a perfect score.
    """
    instructions(name, audio_dir, annotations_dir)  # validate dataset name
    annotation_root = annotations_dir or audio_dir / "annotations"
    suffix = (
        ".key" if name == "giantsteps_key" else ".bpm" if name == "giantsteps_tempo" else ".beats"
    )
    labels = sorted(annotation_root.rglob(f"*{suffix}"))
    audio: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(audio_dir.rglob("*")):
        if path.suffix.lower() in AUDIO_EXTENSIONS:
            audio[path.stem].append(path)
    values: dict[str, list[float]] = defaultdict(list)
    notes: list[str] = []
    digest = hashlib.sha256()
    evaluated = 0
    for label in labels:
        digest.update(label.relative_to(annotation_root).as_posix().encode())
        digest.update(b"\0" + label.read_bytes() + b"\0")
        matches = audio.get(label.stem, [])
        if len(matches) != 1:
            notes.append(f"Excluded {label.name}: {len(matches)} audio matches (expected one).")
            continue
        try:
            ref = read_annotation(label)
        except (ValueError, KeyError, IndexError) as exc:
            notes.append(f"Excluded {label.name}: {exc}")
            continue
        result = analyze(matches[0], use_cache=False)
        evaluated += 1
        if ref.bpm is not None:
            values["tempo_acc1"].append(float(tempo_acc1(result.global_bpm, ref.bpm)))
            values["tempo_acc2"].append(float(tempo_acc2(result.global_bpm, ref.bpm)))
        if ref.beats:
            lo, hi = ref.beats[0] - 0.07, ref.beats[-1] + 0.07
            values["beat_f"].append(
                beat_f_measure([b for b in result.beats if lo <= b <= hi], ref.beats)
            )
            values["downbeat_f"].append(
                beat_f_measure([b for b in result.downbeats if lo <= b <= hi], ref.downbeats)
            )
        if ref.tonic is not None and ref.mode is not None:
            key = result.key
            values["key_mirex"].append(mirex_key_score(key.tonic, key.mode, ref.tonic, ref.mode))
    if not evaluated:
        raise ValueError("no evaluable audio/annotation pairs; " + "; ".join(notes[:5]))
    metrics = {key: statistics.fmean(scores) for key, scores in values.items()}
    metrics.update(
        evaluated=float(evaluated),
        excluded=float(len(labels) - evaluated),
        annotations=float(len(labels)),
    )
    return new_result(
        "dataset",
        metrics,
        backends=registry.versions(registry.selection(None)),
        parameters={"dataset": name, "annotations_sha256": digest.hexdigest()},
        notes=[
            "Local user-supplied audio; no redistribution. Macro-average by track.",
            "Rhythm scoring uses the annotated interval; tempo from median IBI.",
            *notes,
        ],
    )
