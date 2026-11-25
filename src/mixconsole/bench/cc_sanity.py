"""CC0/CC-BY real-music sanity set; audio stays in the ignored cache."""

import hashlib
import html
import re
import statistics
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from mixconsole.analysis import analyze, registry
from mixconsole.analysis.cache import cache_root
from mixconsole.bench.metrics import tempo_acc1, tempo_acc2
from mixconsole.bench.results import BenchResult, new_result

MANIFEST = Path(__file__).resolve().parents[3] / "bench" / "datasets" / "cc_sanity.yaml"
NOTES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


class Track(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    title: str
    artist: str
    genre: str
    license: str = Field(pattern=r"^CC(?:0-1\.0|-BY-(?:3\.0|4\.0))$")
    bpm: float | None = Field(default=None, gt=0)
    source_url: HttpUrl
    audio_url: HttpUrl | None = None


def tracks() -> list[Track]:
    """Load the reviewed source and license metadata."""
    raw = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    entries = [Track.model_validate(item) for item in raw["tracks"]]
    if len({entry.id for entry in entries}) != len(entries):
        raise ValueError("duplicate CC sanity track ID")
    return entries


def _request(url: str) -> Request:
    return Request(url, headers={"User-Agent": "MixConsole/0.0.1 (CC sanity benchmark)"})


def fetch_track(track: Track, directory: Path) -> Path:
    """Resolve a reviewed track page and download audio to the ignored cache."""
    destination = directory / f"{track.id}.mp3"
    if destination.is_file() and destination.stat().st_size > 1000:
        return destination
    with urlopen(_request(str(track.source_url)), timeout=30) as response:
        page = response.read().decode("utf-8")
    if track.license == "CC0-1.0":
        if "CC0 1.0 Universal License" not in html.unescape(page):
            raise ValueError(f"license changed or cannot be verified: {track.id}")
        match = re.search(r"https:\\/\\/files\.freemusicarchive\.org\\/[^\" ]+?\.mp3", page)
        if match is None:
            raise ValueError(f"audio URL missing: {track.id}")
        url = html.unescape(match.group().replace("\\/", "/"))
    else:
        if "Attribution (" not in page or f"({track.license[-3:]})" not in page:
            raise ValueError(f"license changed or cannot be verified: {track.id}")
        if track.audio_url is None:
            raise ValueError(f"audio URL missing: {track.id}")
        url = str(track.audio_url)
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=directory, prefix=".cc-", delete=False) as temp:
        temporary = Path(temp.name)
        try:
            with urlopen(_request(url), timeout=60) as response:
                while chunk := response.read(1024 * 1024):
                    temp.write(chunk)
                temp.flush()
            if temporary.stat().st_size < 1000:
                raise ValueError(f"empty download: {track.id}")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return destination


def run_cc_sanity(*, fetch: bool = False, beats: str = "librosa") -> BenchResult:
    """Analyze reviewed CC tracks; record per-track outputs and plausible-range flags."""
    entries = tracks()
    root = cache_root()
    directory = root / "datasets" / "cc_sanity"
    metrics: dict[str, float] = {}
    notes: list[str] = []
    bpm_scores: list[float] = []
    bpm_octave_scores: list[float] = []
    evaluated = 0
    for track in entries:
        try:
            path = fetch_track(track, directory) if fetch else directory / f"{track.id}.mp3"
        except OSError as exc:
            notes.append(f"Fetch failed {track.id}: {exc}")
            continue
        if not path.is_file():
            notes.append(f"Missing {track.id}: run with --fetch")
            continue
        result = analyze(path, backends={"beats": beats}, use_cache=True, cache_dir=root)
        evaluated += 1
        bpm = result.global_bpm or 0.0
        key = f"{NOTES[result.key.tonic]} {result.key.mode}" if result.key else "unknown"
        flags = ["IMPLAUSIBLE BPM"] if not 40 <= bpm <= 240 else []
        if result.beat_confidence < 0.1:
            flags.append("LOW BEAT CONFIDENCE")
        if track.bpm is not None:
            bpm_scores.append(float(tempo_acc1(bpm, track.bpm)))
            bpm_octave_scores.append(float(tempo_acc2(bpm, track.bpm)))
            if not tempo_acc2(bpm, track.bpm):
                flags.append("BPM MISMATCH")
        notes.append(
            f"{track.id} | {track.genre} | {bpm:.2f} BPM | "
            f"reference {track.bpm if track.bpm is not None else 'unknown'} | "
            f"{key} | {len(result.sections)} sections | {', '.join(flags) or 'ok'}"
        )
        metrics[f"bpm_{track.id}"] = bpm
        metrics[f"sections_{track.id}"] = float(len(result.sections))
        metrics[f"beat_confidence_{track.id}"] = result.beat_confidence
    if not evaluated:
        raise ValueError("no cached CC audio; run mixconsole bench dataset cc_sanity --fetch")
    metrics["evaluated"] = float(evaluated)
    metrics["missing"] = float(len(entries) - evaluated)
    if bpm_scores:
        metrics["tempo_acc1_labeled"] = statistics.fmean(bpm_scores)
        metrics["tempo_acc2_labeled"] = statistics.fmean(bpm_octave_scores)
    return new_result(
        "dataset",
        metrics,
        backends=registry.versions(registry.selection({"beats": beats})),
        parameters={
            "dataset": "cc_sanity",
            "beats": beats,
            "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        },
        notes=["Source labels are sparse; unknown BPM is not scored.", *notes],
    )
