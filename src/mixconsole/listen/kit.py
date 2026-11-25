"""Build the listening kit: a folder with ``index.html``, opaque audio files and a private key.

The page never contains system names: audio files and trial items use salted tokens, and the
token -> system map lives in ``key.json`` next to the page (the page does not load it). The page
makes no network requests; votes live in the browser's localStorage and are saved by the rater
as a JSON file, which ``mixconsole listen results`` reads.
"""

import base64
import hashlib
import json
import random
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from mixconsole.listen.page import render_page

MIME = {".m4a": "audio/mp4", ".wav": "audio/wav"}


class InputPair(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    systems: dict[str, str]
    reference: str
    anchor: str


class ListenInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    pairs: list[InputPair]


def _token(seed: int, pair: str, role: str) -> str:
    return hashlib.sha256(f"{seed}|{pair}|{role}".encode()).hexdigest()[:12]


def _encode(source: Path, destination: Path) -> Path:
    """AAC when ffmpeg is present (smaller, plays everywhere), else a plain WAV copy."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is not None:
        target = destination.with_suffix(".m4a")
        command = [
            ffmpeg,
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-map_metadata",
            "-1",
        ]
        command += ["-c:a", "aac", "-b:a", "128k", str(target)]
        if subprocess.run(command, capture_output=True, check=False).returncode == 0:
            return target
    target = destination.with_suffix(".wav")
    shutil.copyfile(source, target)
    return target


def build_kit(
    input_json: Path,
    out: Path,
    *,
    challenger: str = "auto",
    seed: int = 2026,
    embed: bool = False,
    encode: bool = True,
) -> Path:
    """Write ``out/index.html`` (+ ``audio/``, ``key.json``) from a ``listen-input.json``."""
    data = ListenInput.model_validate_json(input_json.read_text(encoding="utf-8"))
    if data.version != "listen-input/v1":
        raise ValueError("unsupported listen input version")
    rng = random.Random(seed)
    audio_dir = out / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    key: dict[str, dict[str, str]] = {}
    files: dict[str, str] = {}

    def add(pair: InputPair, role: str, source: str) -> str:
        token = _token(seed, pair.id, role)
        path = input_json.parent / source
        if not path.is_file():
            raise ValueError(f"missing audio: {path}")
        stored = _encode(path, audio_dir / token) if encode else _plain(path, audio_dir / token)
        key[token] = {"pair": pair.id, "system": role}
        files[token] = f"audio/{stored.name}"
        return token

    ab: list[dict[str, object]] = []
    mushra: list[dict[str, object]] = []
    for pair in data.pairs:
        tokens = {name: add(pair, name, source) for name, source in pair.systems.items()}
        reference = add(pair, "reference", pair.reference)
        visible = add(pair, "reference_visible", pair.reference)
        anchor = add(pair, "anchor", pair.anchor)
        if challenger in tokens:
            for other in sorted(tokens):
                if other == challenger:
                    continue
                sides = [tokens[challenger], tokens[other]]
                rng.shuffle(sides)
                ab.append(
                    {
                        "id": f"{pair.id}:{_token(seed, pair.id, 'ab-' + other)}",
                        "pair": pair.id,
                        "title": pair.title,
                        "left": sides[0],
                        "right": sides[1],
                    }
                )
        mushra.append(
            {
                "pair": pair.id,
                "title": pair.title,
                "reference": visible,
                "items": [*tokens.values(), reference, anchor],
            }
        )
    if not ab and not mushra:
        raise ValueError("no pairs to build a kit from")
    kit_id = hashlib.sha256(json.dumps([ab, mushra], sort_keys=True).encode()).hexdigest()[:10]
    sources = {t: _embed(out / f) for t, f in files.items()} if embed else files
    config: dict[str, object] = {"kit_id": kit_id, "ab": ab, "mushra": mushra, "audio": sources}
    (out / "index.html").write_text(render_page(config), encoding="utf-8")
    (out / "key.json").write_text(
        json.dumps(
            {"kit_id": kit_id, "challenger": challenger, "tokens": key}, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    if embed:
        shutil.rmtree(audio_dir)
    return out / "index.html"


def _plain(source: Path, destination: Path) -> Path:
    target = destination.with_suffix(".wav")
    shutil.copyfile(source, target)
    return target


def _embed(path: Path) -> str:
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{MIME.get(path.suffix, 'application/octet-stream')};base64,{payload}"


def synthetic_input(directory: Path, *, pairs: int = 3) -> Path:
    """Tiny synthetic kit input (no real music): demo and test fixture, 3 crossfade systems."""
    import numpy as np

    from mixconsole.bench.corpus import crossfade, hard_cut
    from mixconsole.io import SAMPLE_RATE, write_audio
    from mixconsole.testing.synth import generate_track

    directory.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    for index in range(pairs):
        a, _ = generate_track(bpm=118 + 4 * index, bars=6, seed=10 + index)
        b, _ = generate_track(bpm=124 + 3 * index, bars=6, seed=20 + index, key="G major")
        variants = {
            "linear6": crossfade(a, b, seconds=2.0),
            "trim_eqpower": crossfade(a, b, seconds=2.0, equal_power=True, trim=True),
            "crossfade4": crossfade(a, b, seconds=4.0, equal_power=True),
        }
        names: dict[str, str] = {}
        for name, rendered in variants.items():
            window = rendered.audio[: 8 * SAMPLE_RATE]
            names[name] = f"p{index}_{name}.wav"
            write_audio(directory / names[name], np.asarray(window, dtype=np.float32))
        write_audio(directory / f"p{index}_ref.wav", a[: 8 * SAMPLE_RATE])
        write_audio(directory / f"p{index}_anchor.wav", hard_cut(a, b).audio[: 8 * SAMPLE_RATE])
        entries.append(
            {
                "id": f"synthetic_{index}",
                "title": f"Synthetic pair {index}",
                "systems": names,
                "reference": f"p{index}_ref.wav",
                "anchor": f"p{index}_anchor.wav",
            }
        )
    path = directory / "listen-input.json"
    path.write_text(
        json.dumps({"version": "listen-input/v1", "pairs": entries}, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
