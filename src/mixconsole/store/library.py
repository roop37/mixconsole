"""Library index (``index.sqlite``): one row per analysed file, batch resumable scan."""

import json
import os
import sqlite3
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from mixconsole.analysis.models import TrackAnalysis
from mixconsole.progress import Cancelled, CancelToken, Progress, checkpoint
from mixconsole.store.db import connect

AUDIO_SUFFIXES = frozenset(
    {".wav", ".flac", ".mp3", ".ogg", ".oga", ".m4a", ".aac", ".aif", ".aiff"}
)
_NOTES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

MIGRATIONS = (
    """
CREATE TABLE tracks (
  hash TEXT PRIMARY KEY, pcm_sha256 TEXT NOT NULL, path TEXT NOT NULL, duration REAL NOT NULL,
  bpm REAL, key_name TEXT NOT NULL, camelot TEXT NOT NULL, lufs REAL, energy_mean REAL,
  energy_peak REAL, backend_versions TEXT NOT NULL, analyzed_at REAL NOT NULL
);
CREATE TABLE paths (
  path TEXT PRIMARY KEY, hash TEXT NOT NULL REFERENCES tracks(hash) ON DELETE CASCADE,
  size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL, seen_at REAL NOT NULL
);
CREATE INDEX paths_hash ON paths(hash);
CREATE INDEX tracks_bpm ON tracks(bpm);
CREATE INDEX tracks_camelot ON tracks(camelot);
CREATE TABLE failures (path TEXT PRIMARY KEY, error TEXT NOT NULL, failed_at REAL NOT NULL)
""",
)


class LibraryTrack(BaseModel):
    hash: str
    pcm_sha256: str
    path: str
    paths: list[str]
    duration: float
    bpm: float | None
    key: str
    camelot: str
    lufs: float | None
    energy_mean: float | None
    energy_peak: float | None
    backend_versions: dict[str, str]
    analyzed_at: float


class LibraryStats(BaseModel):
    tracks: int
    paths: int
    failures: int
    total_duration: float


@dataclass
class ScanSummary:
    found: int = 0
    analyzed: int = 0
    skipped: int = 0
    failed: int = 0
    errors: dict[str, str] = field(default_factory=dict[str, str])


def energy_summary(analysis: TrackAnalysis) -> tuple[float | None, float | None]:
    values = analysis.arrays.get("bar_energy")
    if values is None or values.size == 0:
        return None, None
    per_bar = values.sum(axis=1) if values.ndim == 2 else values
    return float(per_bar.mean()), float(per_bar.max())


class LibraryIndex:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _row(self, conn: sqlite3.Connection, row: sqlite3.Row) -> LibraryTrack:
        paths = [
            r["path"]
            for r in conn.execute(
                "SELECT path FROM paths WHERE hash=? ORDER BY path", (row["hash"],)
            )
        ]
        return LibraryTrack(
            hash=row["hash"],
            pcm_sha256=row["pcm_sha256"],
            path=row["path"],
            paths=paths,
            duration=row["duration"],
            bpm=row["bpm"],
            key=row["key_name"],
            camelot=row["camelot"],
            lufs=row["lufs"],
            energy_mean=row["energy_mean"],
            energy_peak=row["energy_peak"],
            backend_versions=json.loads(row["backend_versions"]),
            analyzed_at=row["analyzed_at"],
        )

    def upsert(self, analysis: TrackAnalysis, path: str | Path) -> None:
        source = Path(path)
        stat = source.stat()
        mean, peak = energy_summary(analysis)
        key = f"{_NOTES[analysis.key.tonic]} {analysis.key.mode}"
        now = time.time()
        with connect(self.path, MIGRATIONS) as conn:
            conn.execute(
                "INSERT INTO tracks VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(hash) DO UPDATE SET pcm_sha256=excluded.pcm_sha256, "
                "duration=excluded.duration, bpm=excluded.bpm, key_name=excluded.key_name, "
                "camelot=excluded.camelot, lufs=excluded.lufs, energy_mean=excluded.energy_mean, "
                "energy_peak=excluded.energy_peak, backend_versions=excluded.backend_versions, "
                "analyzed_at=excluded.analyzed_at",
                (
                    analysis.file_sha256,
                    analysis.pcm_sha256,
                    str(source),
                    analysis.duration,
                    analysis.global_bpm,
                    key,
                    analysis.key.camelot,
                    analysis.loudness.integrated_lufs,
                    mean,
                    peak,
                    json.dumps(analysis.backend_versions, sort_keys=True),
                    now,
                ),
            )
            conn.execute(
                "INSERT INTO paths VALUES (?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET "
                "hash=excluded.hash, size=excluded.size, mtime_ns=excluded.mtime_ns, "
                "seen_at=excluded.seen_at",
                (str(source), analysis.file_sha256, stat.st_size, stat.st_mtime_ns, now),
            )
            conn.execute("DELETE FROM failures WHERE path=?", (str(source),))

    def record_failure(self, path: str | Path, error: str) -> None:
        with connect(self.path, MIGRATIONS) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO failures VALUES (?,?,?)", (str(path), error, time.time())
            )

    def get(self, digest: str) -> LibraryTrack | None:
        with connect(self.path, MIGRATIONS, write=False) as conn:
            row = conn.execute("SELECT * FROM tracks WHERE hash=?", (digest,)).fetchone()
            return None if row is None else self._row(conn, row)

    def search(
        self,
        *,
        q: str | None = None,
        bpm_min: float | None = None,
        bpm_max: float | None = None,
        camelot: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[LibraryTrack]:
        where: list[str] = []
        args: list[object] = []
        if q:
            where.append(
                "(path LIKE ? ESCAPE '\\' OR hash LIKE ? OR hash IN "
                "(SELECT hash FROM paths WHERE path LIKE ? ESCAPE '\\'))"
            )
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            args += [f"%{escaped}%", f"{q}%", f"%{escaped}%"]
        if bpm_min is not None:
            where.append("bpm >= ?")
            args.append(bpm_min)
        if bpm_max is not None:
            where.append("bpm <= ?")
            args.append(bpm_max)
        if camelot:
            where.append("camelot = ?")
            args.append(camelot.upper())
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        with connect(self.path, MIGRATIONS, write=False) as conn:
            rows = conn.execute(
                f"SELECT * FROM tracks {clause} ORDER BY path LIMIT ? OFFSET ?",
                (*args, limit, offset),
            ).fetchall()
            return [self._row(conn, r) for r in rows]

    def stats(self) -> LibraryStats:
        with connect(self.path, MIGRATIONS, write=False) as conn:
            tracks, duration = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(duration),0) FROM tracks"
            ).fetchone()
            paths = conn.execute("SELECT COUNT(*) FROM paths").fetchone()[0]
            failures = conn.execute("SELECT COUNT(*) FROM failures").fetchone()[0]
        return LibraryStats(
            tracks=tracks, paths=paths, failures=failures, total_duration=float(duration)
        )

    def known(self) -> dict[str, tuple[int, int, str]]:
        with connect(self.path, MIGRATIONS, write=False) as conn:
            return {
                r["path"]: (r["size"], r["mtime_ns"], r["hash"])
                for r in conn.execute("SELECT path, size, mtime_ns, hash FROM paths")
            }

    def versions_for(self, digest: str) -> dict[str, str] | None:
        track = self.get(digest)
        return None if track is None else track.backend_versions


def find_audio(directory: Path) -> list[Path]:
    found = [
        Path(root, name)
        for root, _, names in os.walk(directory, followlinks=False)
        for name in names
        if Path(name).suffix.lower() in AUDIO_SUFFIXES and not name.startswith(".")
    ]
    return sorted(found)


def scan_library(
    directory: str | Path,
    index: LibraryIndex,
    *,
    workers: int | None = None,
    batch: int | None = None,
    progress: Progress | None = None,
    cancel: CancelToken | None = None,
    paths: Sequence[Path] | None = None,
) -> ScanSummary:
    """Analyse every new/changed audio file under ``directory``; safe to kill and rerun.

    Files whose (path, size, mtime) and backend versions already match the index are skipped,
    so a restart resumes where the previous run committed. Results are committed after each
    batch, never held in memory for the whole library. Per-file failures are recorded and do
    not stop the scan.
    """
    from mixconsole.analysis import registry
    from mixconsole.config import load_settings
    from mixconsole.service import analyze_tracks

    settings = load_settings()
    count = workers or settings.workers
    size = batch or max(count * 2, 4)
    summary = ScanSummary()
    files = list(paths) if paths is not None else find_audio(Path(directory))
    summary.found = len(files)
    versions = registry.versions(registry.selection(settings.backends))
    known = index.known()
    todo: list[Path] = []
    for file in files:
        stat = file.stat()
        entry = known.get(str(file))
        if (
            entry
            and entry[:2] == (stat.st_size, stat.st_mtime_ns)
            and index.versions_for(entry[2]) == versions
        ):
            summary.skipped += 1
            continue
        todo.append(file)
    total = max(summary.found, 1)
    checkpoint(progress, cancel, "scan", summary.skipped / total, f"{summary.skipped} up to date")
    for start in range(0, len(todo), size):
        chunk = todo[start : start + size]
        try:
            results = analyze_tracks(chunk, workers=count, cancel=cancel)
        except Exception as exc:
            if isinstance(exc, Cancelled):
                raise
            results: list[TrackAnalysis] = []
            for file in chunk:  # isolate the bad file(s): retry one by one
                try:
                    results += analyze_tracks([file], workers=1, cancel=cancel)
                except Cancelled:
                    raise
                except Exception as single:
                    summary.failed += 1
                    summary.errors[str(file)] = f"{type(single).__name__}: {single}"
                    index.record_failure(file, summary.errors[str(file)])
        for analysis in results:
            index.upsert(analysis, analysis.file)
            summary.analyzed += 1
        done = summary.skipped + summary.analyzed + summary.failed
        checkpoint(progress, cancel, "scan", done / total, f"{done}/{summary.found}")
    checkpoint(progress, cancel, "complete", 1.0)
    return summary
