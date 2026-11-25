"""Persistent job queue: states, progress events, cancellation, RAM-bounded concurrency.

Jobs and their progress events live in ``jobs.sqlite`` so a restart still shows history; jobs
that were queued/running when the process died are marked ``failed`` ("interrupted"). Runners
are plain callables ``(params, progress, cancel) -> result`` that call the service facade.
"""

import json
import os
import threading
import time
import traceback
import uuid
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from mixconsole.progress import Cancelled, CancelToken, Progress, ProgressEvent
from mixconsole.store.db import connect

JobState = Literal["queued", "running", "done", "failed", "cancelled"]
TERMINAL: frozenset[str] = frozenset({"done", "failed", "cancelled"})
Runner = Callable[[dict[str, Any], Progress, CancelToken], dict[str, Any]]

MIGRATIONS = (
    """
CREATE TABLE jobs (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL, project_id TEXT,
  params TEXT NOT NULL, result TEXT, error TEXT, stage TEXT NOT NULL DEFAULT '',
  fraction REAL NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT '', ram_mb INTEGER NOT NULL,
  created_at REAL NOT NULL, started_at REAL, finished_at REAL
);
CREATE INDEX jobs_created ON jobs(created_at);
CREATE TABLE events (
  job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE, seq INTEGER NOT NULL,
  stage TEXT NOT NULL, fraction REAL NOT NULL, message TEXT NOT NULL, ts REAL NOT NULL,
  PRIMARY KEY (job_id, seq)
)
""",
)


class Job(BaseModel):
    id: str
    kind: str
    state: JobState
    project_id: str | None
    params: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    stage: str
    fraction: float
    message: str
    created_at: float
    started_at: float | None
    finished_at: float | None


class JobEvent(BaseModel):
    seq: int
    stage: str
    fraction: float
    message: str
    ts: float


def default_ram_budget_mb() -> int:
    try:
        total = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") // (1024 * 1024)
    except (ValueError, OSError, AttributeError):
        total = 8192
    return max(1024, int(total * 0.6))


def _job(row: Any) -> Job:
    return Job(
        id=row["id"],
        kind=row["kind"],
        state=row["state"],
        project_id=row["project_id"],
        params=json.loads(row["params"]),
        result=json.loads(row["result"]) if row["result"] else None,
        error=row["error"],
        stage=row["stage"],
        fraction=row["fraction"],
        message=row["message"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


class JobManager:
    """Single dispatcher thread admits queued jobs while their summed RAM estimate fits."""

    def __init__(
        self,
        path: Path,
        runners: Mapping[str, Runner],
        *,
        ram_budget_mb: int | None = None,
        ram_cost_mb: Mapping[str, int] | None = None,
        max_concurrent: int = 4,
    ) -> None:
        self.path = path
        self.runners = dict(runners)
        self.budget = ram_budget_mb or default_ram_budget_mb()
        self.costs = {"analyze": 1024, "scan": 1024, "plan": 1024, "render": 2048, "mix": 2048}
        self.costs.update(ram_cost_mb or {})
        self.max_concurrent = max_concurrent
        self._cond = threading.Condition()
        self._tokens: dict[str, CancelToken] = {}
        self._running: dict[str, int] = {}
        self._pool = ThreadPoolExecutor(max_workers=max_concurrent, thread_name_prefix="job")
        self._stop = False
        with connect(self.path, MIGRATIONS) as conn:
            conn.execute(
                "UPDATE jobs SET state='failed', error='interrupted by server restart', "
                "finished_at=? WHERE state IN ('queued','running')",
                (time.time(),),
            )
        self._thread = threading.Thread(target=self._dispatch, name="job-dispatch", daemon=True)
        self._thread.start()

    # public API ---------------------------------------------------------------------------
    def submit(self, kind: str, params: dict[str, Any], project_id: str | None = None) -> Job:
        if kind not in self.runners:
            raise ValueError(f"unknown job kind {kind!r}")
        job_id = uuid.uuid4().hex[:12]
        with connect(self.path, MIGRATIONS) as conn:
            conn.execute(
                "INSERT INTO jobs (id, kind, state, project_id, params, ram_mb, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    job_id,
                    kind,
                    "queued",
                    project_id,
                    json.dumps(params),
                    self.costs.get(kind, 1024),
                    time.time(),
                ),
            )
        with self._cond:
            self._tokens[job_id] = CancelToken()
            self._cond.notify_all()
        job = self.get(job_id)
        assert job is not None
        return job

    def get(self, job_id: str) -> Job | None:
        with connect(self.path, MIGRATIONS, write=False) as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return None if row is None else _job(row)

    def recent(self, *, state: str | None = None, limit: int = 100) -> list[Job]:
        with connect(self.path, MIGRATIONS, write=False) as conn:
            if state:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE state=? ORDER BY created_at DESC, id LIMIT ?",
                    (state, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC, id LIMIT ?", (limit,)
                ).fetchall()
        return [_job(r) for r in rows]

    def events(self, job_id: str, after: int = 0) -> list[JobEvent]:
        with connect(self.path, MIGRATIONS, write=False) as conn:
            rows = conn.execute(
                "SELECT seq, stage, fraction, message, ts FROM events "
                "WHERE job_id=? AND seq>? ORDER BY seq",
                (job_id, after),
            ).fetchall()
        return [JobEvent(**dict(r)) for r in rows]

    def cancel(self, job_id: str) -> Job | None:
        job = self.get(job_id)
        if job is None or job.state in TERMINAL:
            return job
        with self._cond:
            token = self._tokens.get(job_id)
            if token is not None:
                token.cancel()
            if job_id not in self._running:  # still queued: finish it right here
                self._finish(job_id, "cancelled", error="cancelled before start")
            self._cond.notify_all()
        return self.get(job_id)

    def wait(self, job_id: str, timeout: float = 60) -> Job:
        deadline = time.monotonic() + timeout
        while True:
            job = self.get(job_id)
            if job is None or job.state in TERMINAL or time.monotonic() > deadline:
                assert job is not None
                return job
            time.sleep(0.02)

    def shutdown(self) -> None:
        with self._cond:
            self._stop = True
            for token in self._tokens.values():
                token.cancel()
            self._cond.notify_all()
        self._thread.join(timeout=5)
        self._pool.shutdown(wait=True, cancel_futures=True)

    # internals ----------------------------------------------------------------------------
    def _finish(
        self,
        job_id: str,
        state: JobState,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        with connect(self.path, MIGRATIONS) as conn:
            conn.execute(
                "UPDATE jobs SET state=?, result=?, error=?, finished_at=?, "
                "fraction=CASE WHEN ?='done' THEN 1 ELSE fraction END "
                "WHERE id=? AND state IN ('queued','running')",
                (
                    state,
                    None if result is None else json.dumps(result),
                    error,
                    time.time(),
                    state,
                    job_id,
                ),
            )

    def _dispatch(self) -> None:
        while True:
            with self._cond:
                if self._stop:
                    return
                picked = self._next_runnable()
                if picked is None:
                    self._cond.wait(timeout=0.5)
                    continue
                job_id, cost = picked
                self._running[job_id] = cost
            self._pool.submit(self._run, job_id)

    def _next_runnable(self) -> tuple[str, int] | None:
        if len(self._running) >= self.max_concurrent:
            return None
        used = sum(self._running.values())
        with connect(self.path, MIGRATIONS, write=False) as conn:
            rows = conn.execute(
                "SELECT id, ram_mb FROM jobs WHERE state='queued' ORDER BY created_at, id"
            ).fetchall()
        for row in rows:
            if row["id"] in self._running or row["id"] not in self._tokens:
                continue
            # Always allow one job so an oversized request cannot starve the queue forever.
            if not self._running or used + row["ram_mb"] <= self.budget:
                return row["id"], row["ram_mb"]
        return None

    def _run(self, job_id: str) -> None:
        job = self.get(job_id)
        token = self._tokens[job_id]
        try:
            if job is None or job.state != "queued":
                return
            if token.cancelled:
                self._finish(job_id, "cancelled", error="cancelled before start")
                return
            with connect(self.path, MIGRATIONS) as conn:
                conn.execute(
                    "UPDATE jobs SET state='running', started_at=? WHERE id=?",
                    (time.time(), job_id),
                )
            seq = 0
            last = (-1.0, "")

            def progress(event: ProgressEvent) -> None:
                nonlocal seq, last
                key = (round(event.fraction, 3), event.stage)
                if key == last:
                    return
                last = key
                seq += 1
                with connect(self.path, MIGRATIONS) as conn:
                    conn.execute(
                        "INSERT INTO events VALUES (?,?,?,?,?,?)",
                        (job_id, seq, event.stage, event.fraction, event.message, time.time()),
                    )
                    conn.execute(
                        "UPDATE jobs SET stage=?, fraction=?, message=? WHERE id=?",
                        (event.stage, event.fraction, event.message, job_id),
                    )

            try:
                result = self.runners[job.kind]({**job.params, "_job_id": job_id}, progress, token)
            except Cancelled:
                self._finish(job_id, "cancelled", error="cancelled")
            except Exception as exc:
                detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                self._finish(job_id, "failed", error=detail)
            else:
                self._finish(job_id, "done", result=result)
        finally:
            with self._cond:
                self._running.pop(job_id, None)
                self._cond.notify_all()
