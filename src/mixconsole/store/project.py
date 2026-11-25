"""Projects: ``project.sqlite`` + artifact folder. Portable: stored paths are project-relative.

tracks    content-hash keyed, original path kept (and re-pointable), analysis reference
mixscripts append-only versions; ``parent_id`` links an edit to what it was based on
renders   audio + report artifacts produced from a mixscript version
"""

import json
import re
import shutil
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from mixconsole.store.db import connect

MIGRATIONS = (
    """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE tracks (
  hash TEXT PRIMARY KEY, path TEXT NOT NULL, name TEXT NOT NULL, added_at REAL NOT NULL,
  metadata TEXT NOT NULL DEFAULT '{}', analysis_ref TEXT, duration REAL, bpm REAL, camelot TEXT
);
CREATE TABLE mixscripts (
  id TEXT PRIMARY KEY, seq INTEGER NOT NULL UNIQUE, parent_id TEXT REFERENCES mixscripts(id),
  track_a TEXT, track_b TEXT, label TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL,
  document TEXT NOT NULL
);
CREATE TABLE renders (
  id TEXT PRIMARY KEY, mixscript_id TEXT REFERENCES mixscripts(id), folder TEXT NOT NULL,
  audio TEXT NOT NULL, files TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '{}',
  job_id TEXT, created_at REAL NOT NULL
);
CREATE TRIGGER mixscripts_append_only_update BEFORE UPDATE ON mixscripts
  BEGIN SELECT RAISE(ABORT, 'mixscript versions are append-only'); END;
CREATE TRIGGER mixscripts_append_only_delete BEFORE DELETE ON mixscripts
  BEGIN SELECT RAISE(ABORT, 'mixscript versions are append-only'); END
""",
)

_ID = re.compile(r"^[0-9a-f]{12}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")


class ProjectInfo(BaseModel):
    id: str
    name: str
    created_at: float
    tracks: int
    mixscripts: int
    renders: int


class TrackRecord(BaseModel):
    hash: str
    path: str
    name: str
    added_at: float
    metadata: dict[str, Any]
    analyzed: bool
    duration: float | None = None
    bpm: float | None = None
    camelot: str | None = None
    path_exists: bool = True


class MixScriptVersion(BaseModel):
    id: str
    seq: int
    parent_id: str | None
    track_a: str | None
    track_b: str | None
    label: str
    created_at: float


class MixScriptDocument(MixScriptVersion):
    document: dict[str, Any]


class RenderRecord(BaseModel):
    id: str
    mixscript_id: str | None
    audio: str
    files: list[str]
    summary: dict[str, Any]
    job_id: str | None
    created_at: float


def valid_id(value: str) -> bool:
    return bool(_ID.match(value))


def valid_hash(value: str) -> bool:
    return bool(_HASH.match(value))


class Project:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.db = root / "project.sqlite"

    @property
    def id(self) -> str:
        return self.root.name

    @property
    def artifacts(self) -> Path:
        return self.root / "artifacts"

    @classmethod
    def create(cls, projects_dir: Path, name: str) -> "Project":
        project = cls(projects_dir / uuid.uuid4().hex[:12])
        project.artifacts.mkdir(parents=True)
        with connect(project.db, MIGRATIONS) as conn:
            conn.execute("INSERT INTO meta VALUES ('name', ?)", (name,))
            conn.execute("INSERT INTO meta VALUES ('created_at', ?)", (str(time.time()),))
        return project

    def info(self) -> ProjectInfo:
        with connect(self.db, MIGRATIONS, write=False) as conn:
            meta = {r["key"]: r["value"] for r in conn.execute("SELECT * FROM meta")}
            counts = [
                conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("tracks", "mixscripts", "renders")
            ]
        return ProjectInfo(
            id=self.id,
            name=meta["name"],
            created_at=float(meta["created_at"]),
            tracks=counts[0],
            mixscripts=counts[1],
            renders=counts[2],
        )

    def delete(self) -> None:
        shutil.rmtree(self.root)

    # tracks -----------------------------------------------------------------------------
    def _track(self, row: sqlite3.Row) -> TrackRecord:
        return TrackRecord(
            hash=row["hash"],
            path=row["path"],
            name=row["name"],
            added_at=row["added_at"],
            metadata=json.loads(row["metadata"]),
            analyzed=row["analysis_ref"] is not None,
            duration=row["duration"],
            bpm=row["bpm"],
            camelot=row["camelot"],
            path_exists=Path(row["path"]).is_file(),
        )

    def add_track(self, digest: str, path: Path) -> tuple[TrackRecord, bool]:
        with connect(self.db, MIGRATIONS) as conn:
            row = conn.execute("SELECT * FROM tracks WHERE hash=?", (digest,)).fetchone()
            created = row is None
            if created:
                conn.execute(
                    "INSERT INTO tracks (hash, path, name, added_at) VALUES (?,?,?,?)",
                    (digest, str(path), path.name, time.time()),
                )
            elif row["path"] != str(path):
                conn.execute("UPDATE tracks SET path=? WHERE hash=?", (str(path), digest))
            row = conn.execute("SELECT * FROM tracks WHERE hash=?", (digest,)).fetchone()
            return self._track(row), created

    def tracks(self) -> list[TrackRecord]:
        with connect(self.db, MIGRATIONS, write=False) as conn:
            rows = conn.execute("SELECT * FROM tracks ORDER BY added_at, hash").fetchall()
            return [self._track(r) for r in rows]

    def track(self, digest: str) -> TrackRecord | None:
        with connect(self.db, MIGRATIONS, write=False) as conn:
            row = conn.execute("SELECT * FROM tracks WHERE hash=?", (digest,)).fetchone()
            return None if row is None else self._track(row)

    def remove_track(self, digest: str) -> bool:
        with connect(self.db, MIGRATIONS) as conn:
            return conn.execute("DELETE FROM tracks WHERE hash=?", (digest,)).rowcount > 0

    def set_analysis(self, digest: str, ref: str, duration: float, bpm: float | None, camelot: str):
        with connect(self.db, MIGRATIONS) as conn:
            conn.execute(
                "UPDATE tracks SET analysis_ref=?, duration=?, bpm=?, camelot=? WHERE hash=?",
                (ref, duration, bpm, camelot, digest),
            )

    def analysis_path(self, digest: str) -> Path | None:
        with connect(self.db, MIGRATIONS, write=False) as conn:
            row = conn.execute("SELECT analysis_ref FROM tracks WHERE hash=?", (digest,)).fetchone()
        if row is None or row["analysis_ref"] is None:
            return None
        path = self.root / row["analysis_ref"]
        return path if path.is_file() else None

    # mixscripts --------------------------------------------------------------------------
    def _version(self, row: sqlite3.Row) -> MixScriptVersion:
        return MixScriptVersion(
            id=row["id"],
            seq=row["seq"],
            parent_id=row["parent_id"],
            track_a=row["track_a"],
            track_b=row["track_b"],
            label=row["label"],
            created_at=row["created_at"],
        )

    def add_mixscript(
        self,
        document: dict[str, Any],
        *,
        parent_id: str | None = None,
        track_a: str | None = None,
        track_b: str | None = None,
        label: str = "",
    ) -> MixScriptVersion:
        with connect(self.db, MIGRATIONS) as conn:
            if parent_id is not None:
                parent = conn.execute(
                    "SELECT track_a, track_b FROM mixscripts WHERE id=?", (parent_id,)
                ).fetchone()
                if parent is None:
                    raise KeyError(parent_id)
                track_a = track_a or parent["track_a"]
                track_b = track_b or parent["track_b"]
            seq = conn.execute("SELECT COALESCE(MAX(seq),0)+1 FROM mixscripts").fetchone()[0]
            new_id = uuid.uuid4().hex[:12]
            conn.execute(
                "INSERT INTO mixscripts VALUES (?,?,?,?,?,?,?,?)",
                (
                    new_id,
                    seq,
                    parent_id,
                    track_a,
                    track_b,
                    label,
                    time.time(),
                    json.dumps(document, sort_keys=True, allow_nan=False),
                ),
            )
            row = conn.execute("SELECT * FROM mixscripts WHERE id=?", (new_id,)).fetchone()
            return self._version(row)

    def mixscripts(self) -> list[MixScriptVersion]:
        with connect(self.db, MIGRATIONS, write=False) as conn:
            rows = conn.execute("SELECT * FROM mixscripts ORDER BY seq").fetchall()
            return [self._version(r) for r in rows]

    def mixscript(self, version_id: str) -> MixScriptDocument | None:
        with connect(self.db, MIGRATIONS, write=False) as conn:
            row = conn.execute("SELECT * FROM mixscripts WHERE id=?", (version_id,)).fetchone()
            if row is None:
                return None
            return MixScriptDocument(
                **self._version(row).model_dump(), document=json.loads(row["document"])
            )

    # renders -----------------------------------------------------------------------------
    def _render(self, row: sqlite3.Row) -> RenderRecord:
        return RenderRecord(
            id=row["id"],
            mixscript_id=row["mixscript_id"],
            audio=row["audio"],
            files=json.loads(row["files"]),
            summary=json.loads(row["summary"]),
            job_id=row["job_id"],
            created_at=row["created_at"],
        )

    def add_render(
        self,
        render_id: str,
        *,
        mixscript_id: str | None,
        audio: str,
        files: list[str],
        summary: dict[str, Any],
        job_id: str | None,
    ) -> RenderRecord:
        with connect(self.db, MIGRATIONS) as conn:
            conn.execute(
                "INSERT INTO renders VALUES (?,?,?,?,?,?,?,?)",
                (
                    render_id,
                    mixscript_id,
                    f"artifacts/renders/{render_id}",
                    audio,
                    json.dumps(files),
                    json.dumps(summary),
                    job_id,
                    time.time(),
                ),
            )
            row = conn.execute("SELECT * FROM renders WHERE id=?", (render_id,)).fetchone()
            return self._render(row)

    def renders(self) -> list[RenderRecord]:
        with connect(self.db, MIGRATIONS, write=False) as conn:
            rows = conn.execute("SELECT * FROM renders ORDER BY created_at, id").fetchall()
            return [self._render(r) for r in rows]

    def render(self, render_id: str) -> RenderRecord | None:
        with connect(self.db, MIGRATIONS, write=False) as conn:
            row = conn.execute("SELECT * FROM renders WHERE id=?", (render_id,)).fetchone()
            return None if row is None else self._render(row)

    def render_dir(self, render_id: str) -> Path:
        return self.artifacts / "renders" / render_id


class ProjectStore:
    def __init__(self, data_dir: Path) -> None:
        self.dir = data_dir / "projects"

    def create(self, name: str) -> Project:
        return Project.create(self.dir, name)

    def get(self, project_id: str) -> Project | None:
        if not valid_id(project_id):
            return None
        project = Project(self.dir / project_id)
        return project if project.db.is_file() else None

    def list(self) -> list[ProjectInfo]:
        if not self.dir.is_dir():
            return []
        found = [Project(p) for p in sorted(self.dir.iterdir()) if (p / "project.sqlite").is_file()]
        return sorted((p.info() for p in found), key=lambda i: (i.created_at, i.id))
