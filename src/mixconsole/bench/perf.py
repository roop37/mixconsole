"""Per-stage wall time and peak Python-heap memory on generated synthetic inputs."""

import resource
import statistics
import sys
import tempfile
import time
import tracemalloc
from collections.abc import Callable, Sequence
from pathlib import Path

from mixconsole.analysis import analyze, registry
from mixconsole.analysis.features import extract
from mixconsole.bench.results import BenchResult, new_result
from mixconsole.io import load_audio, write_audio
from mixconsole.testing.synth import generate_track

Progress = Callable[[str], None]


def _median_seconds(call: Callable[[], object], repeat: int) -> float:
    times: list[float] = []
    for _ in range(repeat):
        start = time.perf_counter()
        call()
        times.append(time.perf_counter() - start)
    return statistics.median(times)


def _peak_heap_bytes(call: Callable[[], object]) -> float:
    tracemalloc.start()
    try:
        call()
        return float(tracemalloc.get_traced_memory()[1])
    finally:
        tracemalloc.stop()


def _quiet(_message: str) -> None:
    """Default progress sink."""


def _bench_duration(
    root: Path, seconds: int, repeat: int, bpm: float, say: Progress
) -> dict[str, float]:
    names = registry.selection(None)
    say(f"perf: generating {seconds}s input")
    bars = max(2, round(seconds / (60 / bpm * 4)))
    audio, _ = generate_track(bpm=bpm, bars=bars, seed=1)
    path = write_audio(root / f"{seconds}.wav", audio)
    decoded = load_audio(path)
    features = extract(decoded.samples, decoded.sample_rate)
    sr = decoded.sample_rate
    stages: dict[str, Callable[[], object]] = {
        "decode": lambda: load_audio(path),
        "features": lambda: extract(decoded.samples, sr),
        "beats": lambda: registry.BEATS[names["beats"]].analyze(features, sr),
        "key": lambda: registry.KEYS[names["key"]].analyze(features),
        "loudness": lambda: registry.LOUDNESS[names["loudness"]].analyze(decoded.samples, sr),
        "sections": lambda: registry.SECTIONS[names["sections"]].analyze(
            features, decoded.duration
        ),
        "cues": lambda: registry.CUES[names["cues"]].analyze(decoded.samples, sr, bpm),
        "analyze_cold": lambda: analyze(path, use_cache=False),
    }
    metrics: dict[str, float] = {}
    for stage, call in stages.items():
        say(f"perf: {stage} @ {seconds}s")
        metrics[f"{stage}_{seconds}s"] = _median_seconds(call, repeat)
    cache = root / f"cache-{seconds}"
    analyze(path, cache_dir=cache)
    metrics[f"analyze_cache_hit_{seconds}s"] = _median_seconds(
        lambda: analyze(path, cache_dir=cache), repeat
    )
    say(f"perf: peak heap @ {seconds}s")
    heap = _peak_heap_bytes(lambda: analyze(path, use_cache=False))
    metrics[f"peak_heap_mib_{seconds}s"] = heap / 2**20
    metrics[f"realtime_factor_{seconds}s"] = seconds / metrics[f"analyze_cold_{seconds}s"]
    return metrics


def run_perf(
    durations: Sequence[int] = (30, 240, 600),
    repeat: int = 3,
    bpm: float = 124.0,
    progress: Progress | None = None,
) -> BenchResult:
    """Time decode, features, each default backend, cold analyze and a cache hit.

    Metrics are medians over ``repeat`` runs, named ``<stage>_<duration>s``. Peak heap is
    measured once per duration with tracemalloc (NumPy allocations are traced), separately
    from timing so tracing overhead does not skew the times.
    """
    say = progress or _quiet
    metrics: dict[str, float] = {}
    with tempfile.TemporaryDirectory(prefix="mixconsole-bench-") as tmp:
        for seconds in durations:
            metrics.update(_bench_duration(Path(tmp), seconds, repeat, bpm, say))
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    metrics["process_max_rss_mib"] = rss / (2**20 if sys.platform == "darwin" else 2**10)
    if 240 in durations:
        metrics["analyze_240s_cold"] = metrics["analyze_cold_240s"]
        metrics["analyze_cache_hit"] = metrics["analyze_cache_hit_240s"]
    return new_result(
        "perf",
        metrics,
        backends=registry.versions(registry.selection(None)),
        parameters={"durations": list(durations), "repeat": repeat, "bpm": bpm},
        notes=[
            "Synthetic input (mixconsole.testing.synth); real music may differ.",
            "peak_heap_mib is Python/NumPy heap via tracemalloc, not full process RSS.",
        ],
    )
