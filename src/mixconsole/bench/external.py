"""Optional external baseline: VertexSelection/automix-engine (LGPL-2.1).

Run strictly as a separate process from its own venv under the cache (see
``scripts/setup_automix_engine.sh``). Nothing of it is imported or vendored here.
"""

import json
import shutil
import subprocess
import time
from pathlib import Path

from mixconsole.analysis.cache import cache_root
from mixconsole.bench.corpus import (
    CorpusPair,
    centered_excerpt,
    make_row,
    metrics_row,
    write_excerpt,
)
from mixconsole.io import SAMPLE_RATE, load_audio
from mixconsole.verify.metrics import verify_seam

TIMEOUT_SECONDS = 900


def engine_root() -> Path:
    return cache_root() / "external" / "automix-engine"


def available() -> bool:
    return (engine_root() / "READY").is_file()


def run_automix_engine(
    pair: CorpusPair, a: Path, b: Path, work: Path, excerpts: Path | None
) -> dict[str, object]:
    """Render one pair in a scratch copy of the engine; failures become ``failed`` rows."""
    started = time.perf_counter()
    root = engine_root()
    if not available():
        return make_row(pair, "automix_engine", "failed", 0.0, reason="not set up (see M4 notes)")
    folder = work / f"{pair.id}__automix"
    shutil.rmtree(folder, ignore_errors=True)
    shutil.copytree(root / "src", folder, ignore=shutil.ignore_patterns(".git"))
    try:
        # The engine wants clean 44.1 kHz stereo MP3s named song1/song2.
        for name, source in (("song1", a), ("song2", b)):
            command = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(source)]
            command += ["-ar", "44100", "-ac", "2", "-c:a", "libmp3lame", "-b:a", "256k"]
            subprocess.run([*command, str(folder / f"{name}.mp3")], check=True, capture_output=True)
        subprocess.run(
            [str(root / "venv" / "bin" / "python"), "stem_transition.py"],
            cwd=folder,
            check=True,
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
        )
        output = folder / "output" / "beat_overlap"
        report = json.loads((output / "beat_overlap_transition_report.json").read_text())
        mix = load_audio(output / "beat_overlap_transition.wav").samples
    except (OSError, subprocess.SubprocessError, ValueError, KeyError) as exc:
        shutil.rmtree(folder, ignore_errors=True)
        return make_row(
            pair, "automix_engine", "failed", time.perf_counter() - started, reason=str(exc)[:200]
        )
    seam = round(float(report["song1_transition_start_seconds"]) * SAMPLE_RATE)
    length = round(float(report["transition_seconds"]) * SAMPLE_RATE)
    bpm = float(report.get("song1_matched_pulse_bpm") or 120.0)
    metric = verify_seam(mix, seam, length, bpm=bpm)  # no separated stems: overlap n/a
    path = None
    if excerpts is not None:
        path = write_excerpt(
            excerpts, pair, "automix_engine", centered_excerpt(mix, seam + length // 2)
        )
    shutil.rmtree(folder, ignore_errors=True)
    return make_row(
        pair,
        "automix_engine",
        "ok",
        time.perf_counter() - started,
        family="external",
        excerpt=path,
        **metrics_row(metric, length / SAMPLE_RATE),
    )
