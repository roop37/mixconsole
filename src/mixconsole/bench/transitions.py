"""Seeded synthetic M2 transition benchmark; all audio stays in a temporary folder."""

import time
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

import numpy as np

from mixconsole.bench.results import BenchResult, new_result
from mixconsole.io import SAMPLE_RATE, write_audio
from mixconsole.render.graph import RenderInspection
from mixconsole.render.limiter import true_peak_dbtp
from mixconsole.service import mix_pair
from mixconsole.testing.synth import generate_track
from mixconsole.verify.metrics import verify_seam

type Percussion = Literal["click", "kick", "both", "sparse", "none"]


def _fixture(
    path: Path,
    *,
    bpm: float,
    key: str = "C major",
    percussion: Percussion = "both",
    fade: bool = False,
    noise: bool = False,
) -> None:
    audio, _ = generate_track(bpm=bpm, bars=32, key=key, percussion=percussion, seed=7)
    if fade:
        count = min(len(audio), SAMPLE_RATE * 4)
        audio[-count:] *= np.linspace(1, 0, count, dtype=np.float32)[:, None]
    if noise:
        rng = np.random.default_rng(2026)
        rms = float(np.sqrt(np.mean(audio * audio)))
        audio += rng.normal(0, rms / 10, audio.shape).astype(np.float32)
    write_audio(path, audio)


def _baseline(a: Path, b: Path) -> dict[str, float | None]:
    from mixconsole.io import load_audio

    started = time.perf_counter()
    left, right = load_audio(a).samples, load_audio(b).samples
    count = min(len(left), len(right), 6 * SAMPLE_RATE)
    fade = np.linspace(0, 1, count, dtype=np.float32)[:, None]
    joined = np.concatenate(
        (left[:-count], left[-count:] * (1 - fade) + right[:count] * fade, right[count:])
    )
    joined = joined.astype(np.float32)
    # Separated contributions let the baseline's bass overlap be measured, not assumed 0.
    inspection = RenderInspection(
        contribution_a=(left[-count:] * (1 - fade)).astype(np.float32),
        contribution_b=(right[:count] * fade).astype(np.float32),
    )
    metric = verify_seam(joined, len(left) - count, count, bpm=120, inspection=inspection)
    return {
        "pass_rate": float(metric.passed),
        "drift_ms": metric.drift_ms,
        "dip_lu": metric.loudness_dip_lu,
        "bump_lu": metric.loudness_bump_lu,
        "true_peak_dbtp": true_peak_dbtp(joined),
        "low_overlap_bars": metric.low_overlap_bars,
        "length_seconds": 6.0,
        "seconds": time.perf_counter() - started,
    }


def run_transitions(*, quick: bool = False) -> BenchResult:
    """Measure pass rate, seam metrics and runtime per chosen family plus a 6 s baseline."""
    cases: list[tuple[str, float, float, str, str, Percussion, bool, bool]] = [
        ("same", 120.0, 120.0, "C major", "C major", "both", True, False),
        ("plus3", 120.0, 123.6, "C major", "C major", "both", True, False),
        ("minus7", 120.0, 111.6, "C major", "C major", "both", True, False),
        ("overstretch", 100.0, 130.0, "C major", "C major", "both", True, False),
        ("halftime", 120.0, 60.0, "C major", "C major", "both", True, False),
        ("beatless", 120.0, 120.0, "C major", "C major", "none", True, False),
        ("hard_end", 120.0, 120.0, "C major", "C major", "both", False, False),
        ("fade_out", 120.0, 120.0, "C major", "C major", "both", True, False),
        ("key_clash", 120.0, 120.0, "C major", "F# major", "both", True, False),
        ("snr20", 120.0, 120.0, "C major", "C major", "both", True, True),
    ]
    if quick:
        cases = cases[:2]
    sums: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    notes: list[str] = []
    with TemporaryDirectory(prefix="mixconsole-m2-bench-") as temporary:
        root = Path(temporary)
        for name, bpm_a, bpm_b, key_a, key_b, percussion, fade, noise in cases:
            folder = root / name
            folder.mkdir()
            a, b = folder / "a.wav", folder / "b.wav"
            _fixture(a, bpm=bpm_a, key=key_a, fade=fade, noise=noise)
            _fixture(b, bpm=bpm_b, key=key_b, percussion=percussion, noise=noise)
            started = time.perf_counter()
            try:
                result = mix_pair(a, b, out=folder / "mix.wav", report_dir=folder / "report")
                elapsed = time.perf_counter() - started
                family = result.mixscript.transitions[0].family
                metric = result.metrics
                if metric is None:
                    raise RuntimeError("missing verification metrics")
                sums[family]["pass_rate"].append(float(metric.passed))
                if metric.drift_ms is not None:
                    sums[family]["drift_ms"].append(metric.drift_ms)
                sums[family]["dip_lu"].append(metric.loudness_dip_lu)
                sums[family]["bump_lu"].append(metric.loudness_bump_lu)
                sums[family]["true_peak_dbtp"].append(metric.true_peak_dbtp)
                if metric.low_overlap_bars is not None:
                    sums[family]["low_overlap_bars"].append(metric.low_overlap_bars)
                sums[family]["length_bars"].append(
                    float(result.mixscript.transitions[0].length_bars)
                )
                sums[family]["seconds"].append(elapsed)
                notes.append(f"{name}: {family}, {'pass' if metric.passed else metric.reason}")
            except (ValueError, OSError, RuntimeError) as exc:
                notes.append(f"{name}: failed ({exc})")
            baseline = _baseline(a, b)
            for key, value in baseline.items():
                if value is not None:
                    sums["baseline_6s_linear"][key].append(value)
    metrics = {
        f"{family}_{measure}": float(np.mean(values))
        for family, measurements in sums.items()
        for measure, values in measurements.items()
    }
    return new_result("transitions", metrics, parameters={"cases": len(cases)}, notes=notes)
