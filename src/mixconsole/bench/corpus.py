"""Transition corpus benchmark (M4): every pair x system, seam metrics, excerpts for listening.

Audio comes only from Creative Commons tracks fetched by :func:`fetch_corpus` into the ignored
cache. Unmeasured metrics stay absent/``None`` and print as ``n/a``; they are never zero.
"""

import html
import json
import re
import statistics
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.request import Request, urlopen

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from mixconsole.analysis.cache import cache_root
from mixconsole.bench.results import BenchResult, new_result
from mixconsole.io import SAMPLE_RATE, Audio, load_audio, write_audio
from mixconsole.mixscript import MixScript
from mixconsole.render.graph import RenderInspection
from mixconsole.verify.metrics import SeamMetrics, verify_seam

PAIRS = Path(__file__).resolve().parents[3] / "bench" / "pairs.yaml"
BASELINES = ("linear6", "trim_eqpower")
MIXCONSOLE = ("smooth", "auto", "club")
EXTERNAL = ("automix_engine",)
SYSTEMS = (*BASELINES, *MIXCONSOLE)
EXCERPT_SECONDS = 40.0
# Reported measure -> key in a row.
MEASURES = {
    "drift_ms": "drift_ms",
    "dip_lu": "loudness_dip_lu",
    "bump_lu": "loudness_bump_lu",
    "true_peak_dbtp": "true_peak_dbtp",
    "clicks": "clicks",
    "low_overlap_bars": "low_overlap_bars",
    "vocal_overlap_seconds": "vocal_overlap_seconds",
    "bass_overlap_bars": "bass_overlap_bars",
    "seconds": "seconds",
}


class CorpusTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    title: str
    artist: str
    genre: str
    license: str = Field(pattern=r"^CC(?:0-1\.0|-BY-(?:3\.0|4\.0))$")
    source_url: HttpUrl
    attribution: str
    audio_url: HttpUrl | None = None


class CorpusPair(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    a: str
    b: str
    kind: Literal["same-genre", "cross-genre"]


class Corpus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tracks: list[CorpusTrack]
    pairs: list[CorpusPair]

    def track(self, track_id: str) -> CorpusTrack:
        return next(t for t in self.tracks if t.id == track_id)


def load_corpus(path: Path = PAIRS) -> Corpus:
    """Load and cross-check the reviewed manifest."""
    corpus = Corpus.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    ids = [t.id for t in corpus.tracks]
    if len(set(ids)) != len(ids) or len({p.id for p in corpus.pairs}) != len(corpus.pairs):
        raise ValueError("duplicate corpus track or pair ID")
    for pair in corpus.pairs:
        if pair.a not in ids or pair.b not in ids or pair.a == pair.b:
            raise ValueError(f"pair {pair.id} references an unknown or identical track")
    return corpus


def run_order(corpus: Corpus) -> list[CorpusPair]:
    """Deterministic interleave so a --limit or time budget still spans every genre block."""
    pairs = corpus.pairs
    return [*pairs[0::3], *pairs[1::3], *pairs[2::3]]


def corpus_audio_dir(root: Path | None = None) -> Path:
    return (root or cache_root()) / "corpus" / "audio"


def page_license(page: str) -> str | None:
    """Per-track licence read from a Free Music Archive track page; None if not CC0 / CC-BY."""
    text = html.unescape(page)
    if "CC0 1.0 Universal" in text:
        return "CC0-1.0"
    match = re.search(r"Attribution (\d\.\d) (?:International|Generic)\s+License", text)
    return f"CC-BY-{match.group(1)}" if match else None


def _request(url: str) -> Request:
    return Request(url, headers={"User-Agent": "MixConsole/0.0.1 (CC corpus benchmark)"})


def fetch_track(track: CorpusTrack, directory: Path) -> Path:
    """Verify the live licence on the track page, then download the audio into the cache."""
    destination = directory / f"{track.id}.mp3"
    if destination.is_file() and destination.stat().st_size > 1000:
        return destination
    with urlopen(_request(str(track.source_url)), timeout=30) as response:
        page = response.read().decode("utf-8")
    if page_license(page) != track.license:
        raise ValueError(f"license changed or cannot be verified: {track.id}")
    url = str(track.audio_url) if track.audio_url else None
    if url is None:
        found = re.search(r"https:\\/\\/files\.freemusicarchive\.org\\/[^\" ]+?\.mp3", page)
        if found is None:
            raise ValueError(f"audio URL missing: {track.id}")
        url = html.unescape(found.group().replace("\\/", "/"))
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=directory, prefix=".cc-", delete=False) as temp:
        temporary = Path(temp.name)
        try:
            with urlopen(_request(url), timeout=90) as response:
                while chunk := response.read(1024 * 1024):
                    temp.write(chunk)
                temp.flush()
            if temporary.stat().st_size < 1000:
                raise ValueError(f"empty download: {track.id}")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return destination


def fetch_corpus(corpus: Corpus, directory: Path, track_ids: set[str] | None = None) -> list[str]:
    """Fetch every needed track; returns human-readable failures (empty when all present)."""
    failures: list[str] = []
    for track in corpus.tracks:
        if track_ids is not None and track.id not in track_ids:
            continue
        try:
            fetch_track(track, directory)
        except (OSError, ValueError) as exc:
            failures.append(f"{track.id}: {exc}")
    return failures


# ---- baseline systems -------------------------------------------------------------------


def _trim(audio: Audio, *, head: bool, threshold_db: float = -50.0) -> Audio:
    level = np.max(np.abs(audio), axis=1)
    loud = np.flatnonzero(level > 10 ** (threshold_db / 20))
    if not len(loud):
        return audio
    return audio[loud[0] :] if head else audio[: loud[-1] + 1]


@dataclass
class Rendered:
    """A seam excerpt: the joined audio, where the overlap starts and how long it is."""

    audio: Audio
    seam: int
    length: int
    inspection: RenderInspection = field(default_factory=RenderInspection)


def crossfade(
    a: Audio, b: Audio, *, seconds: float = 6.0, equal_power: bool = False, trim: bool = False
) -> Rendered:
    """Plain crossfade of A's tail into B's head. ``trim`` strips silence first."""
    context = 45 * SAMPLE_RATE
    left = a[-context:]
    right = b[:context]
    if trim:
        left, right = _trim(left, head=False), _trim(right, head=True)
    count = min(len(left), len(right), round(seconds * SAMPLE_RATE))
    ramp = np.linspace(0, 1, count, dtype=np.float32)[:, None]
    fade_in = np.sin(ramp * np.pi / 2) if equal_power else ramp
    fade_out = np.cos(ramp * np.pi / 2) if equal_power else 1 - ramp
    out = (left[-count:] * fade_out).astype(np.float32)
    inn = (right[:count] * fade_in).astype(np.float32)
    joined = np.concatenate((left[:-count], out + inn, right[count:])).astype(np.float32)
    return Rendered(
        joined,
        len(left) - count,
        count,
        RenderInspection(contribution_a=out, contribution_b=inn),
    )


def hard_cut(a: Audio, b: Audio) -> Rendered:
    """Listening-test anchor: A stops dead, B starts dead, no overlap at all."""
    left, right = a[-20 * SAMPLE_RATE :], b[: 20 * SAMPLE_RATE]
    return Rendered(np.concatenate((left, right)).astype(np.float32), len(left), 0)


def centered_excerpt(audio: Audio, center: int, seconds: float = EXCERPT_SECONDS) -> Audio:
    """``seconds`` of audio around ``center``, shifted inside the file when near an edge."""
    size = min(len(audio), round(seconds * SAMPLE_RATE))
    start = min(max(0, center - size // 2), len(audio) - size)
    return audio[start : start + size]


# ---- running --------------------------------------------------------------------------


def make_row(
    pair: CorpusPair, system: str, status: str, seconds: float, **extra: object
) -> dict[str, object]:
    return {"pair": pair.id, "system": system, "status": status, "seconds": seconds, **extra}


def metrics_row(metric: SeamMetrics, length_seconds: float) -> dict[str, object]:
    # Seam metrics are kept as measured: None stays None (not applicable / not measurable).
    data: dict[str, object] = dict(metric.as_dict())
    data["pass"] = data.pop("passed")
    data["length_seconds"] = length_seconds
    return data


def run_baseline(
    pair: CorpusPair, system: str, a: Audio, b: Audio, bpm: float, excerpts: Path | None
) -> dict[str, object]:
    started = time.perf_counter()
    rendered = crossfade(a, b, equal_power=system == "trim_eqpower", trim=system == "trim_eqpower")
    metric = verify_seam(
        rendered.audio, rendered.seam, rendered.length, bpm=bpm, inspection=rendered.inspection
    )
    path = None
    if excerpts is not None:
        path = write_excerpt(
            excerpts,
            pair,
            system,
            centered_excerpt(rendered.audio, rendered.seam + rendered.length // 2),
        )
    return make_row(
        pair,
        system,
        "ok",
        time.perf_counter() - started,
        family="crossfade",
        excerpt=path,
        **metrics_row(metric, rendered.length / SAMPLE_RATE),
    )


def write_excerpt(folder: Path, pair: CorpusPair, system: str, audio: Audio) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{pair.id}__{system}.wav"
    write_audio(folder / name, audio)
    return name


def transition_midpoint(script: MixScript, fallback_bpm: float) -> int:
    """Frame of the middle of the rendered transition, from the MixScript cue and length."""
    transition = script.transitions[0]
    points = transition.tempo.tempo_map
    bpm = points[0].bpm if points else fallback_bpm
    length = transition.length_bars * transition.beats_per_bar * 60 / bpm
    return round((transition.exit.seconds + length / 2) * SAMPLE_RATE)


def run_mixconsole(
    pair: CorpusPair,
    style: str,
    a: Path,
    b: Path,
    bpm: float,
    work: Path,
    excerpts: Path | None,
) -> dict[str, object]:
    from mixconsole.service import mix_pair

    started = time.perf_counter()
    folder = work / f"{pair.id}__{style}"
    try:
        result = mix_pair(a, b, style=style, out=folder / "mix.wav", report_dir=folder / "report")
    except (ValueError, OSError, RuntimeError) as exc:
        return make_row(pair, style, "failed", time.perf_counter() - started, reason=str(exc)[:200])
    elapsed = time.perf_counter() - started
    metric = result.metrics
    assert metric is not None
    transition = result.mixscript.transitions[0]
    path = None
    if excerpts is not None:
        mix = load_audio(result.paths["audio"]).samples
        center = transition_midpoint(result.mixscript, bpm)
        path = write_excerpt(excerpts, pair, style, centered_excerpt(mix, center))
    length = transition.length_bars * transition.beats_per_bar * 60 / bpm
    return make_row(
        pair,
        style,
        "ok",
        elapsed,
        family=transition.family,
        chosen=result.chosen_id,
        excerpt=path,
        **metrics_row(metric, length),
    )


def aggregate(rows: list[dict[str, object]], systems: tuple[str, ...]) -> dict[str, float]:
    """Flat ``{system}_{measure}`` means over measured rows only; absent when unmeasured."""
    metrics: dict[str, float] = {}
    for system in systems:
        mine = [r for r in rows if r["system"] == system]
        if not mine:
            continue
        ok = [r for r in mine if r["status"] == "ok"]
        metrics[f"{system}_pairs"] = float(len(mine))
        metrics[f"{system}_error_rate"] = (len(mine) - len(ok)) / len(mine)
        if ok:
            metrics[f"{system}_pass_rate"] = sum(bool(r["pass"]) for r in ok) / len(mine)
        for measure, key in MEASURES.items():
            values = [float(v) for r in ok if isinstance(v := r.get(key), int | float)]
            if values:
                metrics[f"{system}_{measure}"] = statistics.fmean(values)
                metrics[f"{system}_{measure}_n"] = float(len(values))
        families = [str(r["family"]) for r in ok if r.get("family")]
        if families and system in MIXCONSOLE:
            fallback = families.count("fallback") / len(families)
            metrics[f"{system}_fallback_rate"] = fallback
    return metrics


def run_corpus(
    corpus: Corpus,
    audio_dir: Path,
    *,
    systems: tuple[str, ...] = SYSTEMS,
    limit: int | None = None,
    budget_minutes: float | None = None,
    excerpts: Path | None = None,
    work: Path | None = None,
    log: Callable[[str], None] | None = None,
) -> tuple[BenchResult, list[dict[str, object]]]:
    """Render every pair with every system; returns the aggregate result and per-pair rows."""
    from mixconsole.analysis import analyze

    started = time.monotonic()
    pairs = run_order(corpus)[:limit]
    rows: list[dict[str, object]] = []
    notes: list[str] = []
    finished: list[str] = []
    skipped: list[str] = []
    with tempfile.TemporaryDirectory(prefix="mixconsole-corpus-") as scratch:
        folder = work or Path(scratch)
        for pair in pairs:
            if budget_minutes is not None and time.monotonic() - started > budget_minutes * 60:
                skipped.append(pair.id)
                continue
            a_path, b_path = audio_dir / f"{pair.a}.mp3", audio_dir / f"{pair.b}.mp3"
            if not (a_path.is_file() and b_path.is_file()):
                skipped.append(pair.id)
                notes.append(f"{pair.id}: audio missing, run with --fetch")
                continue
            bpm = analyze(a_path).global_bpm or 120.0
            audio_a, audio_b = load_audio(a_path).samples, load_audio(b_path).samples
            for system in systems:
                if system in BASELINES:
                    row = run_baseline(pair, system, audio_a, audio_b, bpm, excerpts)
                elif system in MIXCONSOLE:
                    row = run_mixconsole(pair, system, a_path, b_path, bpm, folder, excerpts)
                else:
                    from mixconsole.bench.external import run_automix_engine

                    row = run_automix_engine(pair, a_path, b_path, folder, excerpts)
                rows.append(row)
                if log:
                    log(f"{pair.id} {system}: {row['status']} {row.get('family', '')}")
            if excerpts is not None:
                _write_reference_and_anchor(excerpts, pair, audio_a, audio_b)
            finished.append(pair.id)
            notes.extend(
                f"{pair.id}/{row['system']}: {row.get('reason', 'failed')}"
                for row in rows
                if row["pair"] == pair.id and row["status"] == "failed"
            )
    if skipped:
        notes.append(f"Not run ({len(skipped)}): {', '.join(skipped)}")
    notes.insert(0, f"Pairs run ({len(finished)}): {', '.join(finished)}")
    result = new_result(
        "corpus",
        aggregate(rows, systems),
        parameters={
            "pairs": len(finished),
            "systems": ",".join(systems),
            "excerpt_seconds": EXCERPT_SECONDS,
        },
        notes=notes,
    )
    return result, rows


def _write_reference_and_anchor(folder: Path, pair: CorpusPair, a: Audio, b: Audio) -> None:
    """Hidden reference (A playing on untouched) and anchor (hard cut) for the listening kit."""
    baseline = crossfade(a, b)
    centre = baseline.seam + baseline.length // 2
    write_excerpt(folder, pair, "reference", centered_excerpt(a[-45 * SAMPLE_RATE :], centre))
    cut = hard_cut(a, b)
    write_excerpt(folder, pair, "anchor", centered_excerpt(cut.audio, cut.seam))


def write_rows(path: Path, corpus: Corpus, rows: list[dict[str, object]]) -> Path:
    """Per-pair x system rows plus the licence table, next to the aggregate result."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": "corpus-rows/v1",
        "tracks": {t.id: t.model_dump(mode="json") for t in corpus.tracks},
        "pairs": {p.id: p.model_dump() for p in corpus.pairs},
        "rows": rows,
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def listen_input(
    corpus: Corpus, rows: list[dict[str, object]], excerpts: Path, systems: tuple[str, ...]
) -> Path:
    """Manifest consumed by ``mixconsole listen build``; paths are relative to ``excerpts``."""
    pairs: list[dict[str, object]] = []
    for pair in run_order(corpus):
        mine = {
            str(r["system"]): str(r["excerpt"])
            for r in rows
            if r["pair"] == pair.id and r.get("excerpt")
        }
        reference = excerpts / f"{pair.id}__reference.wav"
        anchor = excerpts / f"{pair.id}__anchor.wav"
        if not mine or not reference.is_file() or not anchor.is_file():
            continue
        title = f"{corpus.track(pair.a).title} -> {corpus.track(pair.b).title}"
        pairs.append(
            {
                "id": pair.id,
                "title": title,
                "systems": {s: mine[s] for s in systems if s in mine},
                "reference": reference.name,
                "anchor": anchor.name,
            }
        )
    path = excerpts / "listen-input.json"
    path.write_text(
        json.dumps({"version": "listen-input/v1", "pairs": pairs}, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
