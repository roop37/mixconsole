"""Versioned benchmark results with a machine fingerprint, and the LATEST.md summary."""

import json
import os
import platform
import subprocess
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from mixconsole import __version__

# PLAN §5 performance budgets (Apple M4 16 GB reference machine), seconds.
BUDGETS = {"analyze_240s_cold": 20.0, "analyze_cache_hit": 0.2, "process_max_rss_mib": 4096.0}


class Machine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    os: str
    machine: str
    processor: str
    cpu_count: int
    ram_bytes: int | None
    python: str
    packages: dict[str, str]


type BenchKind = Literal["perf", "accuracy", "dataset", "transitions", "corpus"]


class BenchResult(BaseModel):
    """One benchmark run. Metrics are flat name → number maps for easy diffing."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["bench-result/v1"] = "bench-result/v1"
    kind: BenchKind
    created: str
    git_sha: str
    mixconsole: str
    machine: Machine
    backends: dict[str, str] = Field(default_factory=dict)
    parameters: dict[str, float | int | str | list[float] | list[int]] = Field(default_factory=dict)
    metrics: dict[str, float]
    notes: list[str] = Field(default_factory=list)


def _ram_bytes() -> int | None:
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
    except (ValueError, OSError, AttributeError):
        return None


def _processor() -> str:
    if platform.system() == "Darwin":
        try:
            return subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return platform.processor() or platform.machine()


def machine_fingerprint() -> Machine:
    packages: dict[str, str] = {}
    for name in ("numpy", "scipy", "librosa", "soundfile", "pyloudnorm", "torch", "beat-this"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            continue
    return Machine(
        os=f"{platform.system()} {platform.release()}",
        machine=platform.machine(),
        processor=_processor(),
        cpu_count=os.cpu_count() or 1,
        ram_bytes=_ram_bytes(),
        python=platform.python_version(),
        packages=packages,
    )


def git_sha(root: Path) -> str:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
        return sha or "nogit"
    except (OSError, subprocess.SubprocessError):
        return "nogit"


def new_result(
    kind: BenchKind,
    metrics: dict[str, float],
    **extra: object,
) -> BenchResult:
    return BenchResult.model_validate(
        {
            "kind": kind,
            "created": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "git_sha": git_sha(Path.cwd()),
            "mixconsole": __version__,
            "machine": machine_fingerprint(),
            "metrics": metrics,
            **extra,
        }
    )


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")[:40]


def write_result(result: BenchResult, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = result.created[:10]
    kind = result.kind + (
        "-" + _slug(str(result.parameters["dataset"])) if result.kind == "dataset" else ""
    )
    if result.parameters.get("beats", "librosa") != "librosa":
        kind += "-" + _slug(str(result.parameters["beats"]))
    name = f"{stamp}-{kind}-{result.git_sha}-{_slug(result.machine.processor)}.json"
    path = directory / name
    path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    write_latest(directory)
    return path


def load_results(directory: Path) -> list[BenchResult]:
    results: list[BenchResult] = []
    for path in sorted(directory.glob("*.json")):
        try:
            results.append(BenchResult.model_validate_json(path.read_text(encoding="utf-8")))
        except ValueError:
            continue
    return sorted(results, key=lambda r: r.created)


HIGHER_IS_BETTER = ("realtime_factor",)
# Changes smaller than these absolute amounts are timer/allocator noise, never regressions.
NOISE_FLOOR = {"seconds": 0.02, "mib": 8.0}


def _is_regression(name: str, old: float, new: float, threshold: float) -> bool:
    if name.startswith(HIGHER_IS_BETTER):
        return new < old * (1 - threshold)
    floor = NOISE_FLOOR["mib"] if "mib" in name else NOISE_FLOOR["seconds"]
    return new > old * (1 + threshold) and new - old > floor


def compare(old: BenchResult, new: BenchResult, threshold: float = 0.2) -> list[str]:
    """Human-readable % changes. For perf runs, flags slowdowns/memory growth beyond
    ``threshold`` (and an absolute noise floor) and drops in real-time factor."""
    lines: list[str] = []
    for name, value in sorted(new.metrics.items()):
        if name not in old.metrics or old.metrics[name] == 0:
            continue
        before = old.metrics[name]
        change = (value - before) / abs(before)
        flag = ""
        if new.kind == "perf" and _is_regression(name, before, value, threshold):
            flag = "  REGRESSION"
        lines.append(f"{name}: {before:.4g} → {value:.4g} ({change:+.1%}){flag}")
    return lines


CORPUS_COLUMNS = (
    ("pairs", "pairs", "{:.0f}"),
    ("pass_rate", "pass rate", "{:.0%}"),
    ("error_rate", "failed", "{:.0%}"),
    ("fallback_rate", "fallback", "{:.0%}"),
    ("drift_ms", "drift ms", "{:.2f}"),
    ("dip_lu", "dip LU", "{:.2f}"),
    ("bump_lu", "bump LU", "{:.2f}"),
    ("true_peak_dbtp", "peak dBTP", "{:.2f}"),
    ("low_overlap_bars", "low overlap bars", "{:.2f}"),
    ("vocal_overlap_seconds", "vocal overlap s", "{:.2f}"),
    ("bass_overlap_bars", "bass overlap bars", "{:.2f}"),
    ("clicks", "clicks", "{:.1f}"),
    ("seconds", "seconds", "{:.1f}"),
)


def corpus_table(result: BenchResult) -> list[str]:
    """One row per system; a measure that was never measured prints ``n/a``, never 0."""
    systems = str(result.parameters.get("systems", "")).split(",")
    lines = [
        "| system | " + " | ".join(label for _, label, _ in CORPUS_COLUMNS) + " |",
        "|---" * (len(CORPUS_COLUMNS) + 1) + "|",
    ]
    for system in filter(None, systems):
        cells: list[str] = []
        for measure, _, fmt in CORPUS_COLUMNS:
            value = result.metrics.get(f"{system}_{measure}")
            cells.append("n/a" if value is None else fmt.format(value))
        lines.append(f"| {system} | " + " | ".join(cells) + " |")
    return lines


def write_latest(directory: Path) -> Path:
    """Regenerate LATEST.md from the newest result of each kind and beat backend."""
    results = load_results(directory)
    lines = ["# Latest benchmark results", "", "Generated by `mixconsole bench`; do not edit.", ""]
    groups = sorted(
        {
            (
                r.kind,
                str(r.parameters.get("dataset", "")),
                str(r.parameters.get("beats", "librosa")),
                str(r.parameters.get("systems", "")),
            )
            for r in results
        }
    )
    for kind, dataset, beats, systems in groups:
        runs = [
            r
            for r in results
            if r.kind == kind
            and str(r.parameters.get("dataset", "")) == dataset
            and str(r.parameters.get("beats", "librosa")) == beats
            and str(r.parameters.get("systems", "")) == systems
        ]
        if not runs:
            continue
        r = runs[-1]
        lines += [
            f"## {kind}{' ' + dataset if dataset else ''} ({beats}) — {r.created} — {r.git_sha}",
            "",
            (
                f"Machine: {r.machine.processor}, {r.machine.cpu_count} CPUs, "
                f"{(r.machine.ram_bytes or 0) / 2**30:.0f} GiB, {r.machine.os}, "
                f"Python {r.machine.python}"
            ),
            "",
        ]
        if r.kind == "corpus":
            lines += corpus_table(r)
        else:
            lines += ["| metric | value | budget |", "|---|---|---|"]
            for name, value in sorted(r.metrics.items()):
                budget = BUDGETS.get(name)
                mark = (
                    ""
                    if budget is None
                    else (f"≤ {budget} ✓" if value <= budget else f"≤ {budget} ✗")
                )
                lines.append(f"| {name} | {value:.4g} | {mark} |")
        if r.notes:
            lines += ["", *[f"- {note}" for note in r.notes]]
        lines.append("")
    path = directory / "LATEST.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def schema_json() -> str:
    schema = BenchResult.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "urn:mixconsole:bench-result:v1"
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"
