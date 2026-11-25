"""SQLite stores: migrations, append-only history, job queue limits and restart, library scan."""

import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from mixconsole.io import write_audio
from mixconsole.progress import CancelToken, Progress, ProgressEvent
from mixconsole.store.db import connect
from mixconsole.store.jobs import MIGRATIONS as JOB_MIGRATIONS
from mixconsole.store.jobs import JobManager
from mixconsole.store.library import LibraryIndex, find_audio, scan_library
from mixconsole.store.project import MIGRATIONS as PROJECT_MIGRATIONS
from mixconsole.store.project import ProjectStore
from mixconsole.testing.synth import generate_track


def _tracks(directory: Path, count: int, bars: int = 2) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i in range(count):
        audio, _ = generate_track(bpm=90 + i % 60, bars=bars, seed=i)
        paths.append(write_audio(directory / f"t{i:03}.wav", audio))
    return paths


def test_migrations_apply_once_and_reject_newer(tmp_path: Path) -> None:
    db = tmp_path / "x.sqlite"
    with connect(db, ("CREATE TABLE a (x)", "CREATE TABLE b (y)")) as conn:
        conn.execute("INSERT INTO a VALUES (1)")
    with connect(db, ("CREATE TABLE a (x)", "CREATE TABLE b (y)"), write=False) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    with pytest.raises(RuntimeError, match="newer"), connect(db, ("CREATE TABLE a (x)",)):
        pass
    migrations = ("CREATE TABLE a (x)", "CREATE TABLE b (y)")

    def insert_twice() -> None:
        with connect(db, migrations) as conn:
            conn.execute("CREATE TABLE c (z PRIMARY KEY)")
            conn.execute("INSERT INTO c VALUES (1)")
            conn.execute("INSERT INTO c VALUES (1)")

    with pytest.raises(sqlite3.IntegrityError):
        insert_twice()
    with connect(db, ("CREATE TABLE a (x)", "CREATE TABLE b (y)"), write=False) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='c'").fetchone() is None


def test_project_history_is_append_only(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    project = store.create("p")
    assert store.get("../etc") is None and store.get("0" * 12) is None
    first = project.add_mixscript({"v": 1}, track_a="a" * 64, track_b="b" * 64)
    second = project.add_mixscript({"v": 2}, parent_id=first.id)
    assert (second.seq, second.parent_id, second.track_a) == (2, first.id, "a" * 64)
    with pytest.raises(KeyError):
        project.add_mixscript({}, parent_id="missing")
    for sql in ("UPDATE mixscripts SET label='x'", "DELETE FROM mixscripts"):
        with (
            pytest.raises(sqlite3.IntegrityError, match="append-only"),
            connect(project.db, PROJECT_MIGRATIONS) as conn,
        ):
            conn.execute(sql)
    assert project.mixscript(first.id).document == {"v": 1}  # pyright: ignore[reportOptionalMemberAccess]
    info = project.info()
    assert (info.name, info.mixscripts, info.tracks) == ("p", 2, 0)
    assert store.list()[0].id == project.id
    project.delete()
    assert store.list() == []


def _manager(path: Path, runner: Any, **kwargs: Any) -> JobManager:
    return JobManager(path, {"analyze": runner, "render": runner}, **kwargs)


def test_jobs_ram_bound_and_restart_history(tmp_path: Path) -> None:
    lock = threading.Lock()
    live = 0
    peak = 0

    def runner(params: dict[str, Any], progress: Progress, cancel: CancelToken) -> dict[str, Any]:
        nonlocal live, peak
        with lock:
            live += 1
            peak = max(peak, live)
        progress(ProgressEvent("work", 0.5, "half"))
        time.sleep(0.15)
        with lock:
            live -= 1
        return {"echo": params["n"]}

    path = tmp_path / "jobs.sqlite"
    manager = _manager(path, runner, ram_budget_mb=2500, max_concurrent=4)
    jobs = [manager.submit("analyze", {"n": i}) for i in range(5)]  # 1024 MB each: 2 fit in 2500
    done = [manager.wait(j.id, 20) for j in jobs]
    assert [j.state for j in done] == ["done"] * 5
    assert peak == 2
    assert done[0].result == {"echo": 0} and done[0].fraction == 1
    events = manager.events(jobs[0].id)
    assert [(e.stage, e.fraction) for e in events] == [("work", 0.5)]
    big = manager.submit("render", {"n": 9})  # 2048 MB alone still runs (never starves)
    assert manager.wait(big.id, 10).state == "done"
    with pytest.raises(ValueError, match="unknown"):
        manager.submit("nope", {})
    manager.shutdown()

    release = threading.Event()

    def blocked(params: dict[str, Any], progress: Progress, cancel: CancelToken) -> dict[str, Any]:
        release.wait(10)
        return {}

    crashing = _manager(path, blocked, ram_budget_mb=1024, max_concurrent=1)
    first = crashing.submit("analyze", {})
    queued = crashing.submit("analyze", {})
    deadline = time.time() + 5
    while crashing.get(first.id).state != "running" and time.time() < deadline:  # pyright: ignore[reportOptionalMemberAccess]
        time.sleep(0.02)
    cancelled = crashing.cancel(queued.id)
    assert cancelled is not None and cancelled.state == "cancelled"
    release.set()
    crashing.shutdown()

    # Simulate a crash: rows left running/queued become failed on the next start.
    with connect(path, JOB_MIGRATIONS) as conn:
        conn.execute("UPDATE jobs SET state='running', finished_at=NULL WHERE id=?", (first.id,))
    revived = _manager(path, blocked)
    assert revived.get(first.id).state == "failed"  # pyright: ignore[reportOptionalMemberAccess]
    assert "restart" in (revived.get(first.id).error or "")  # pyright: ignore[reportOptionalMemberAccess]
    assert len(revived.recent()) >= 8
    assert revived.recent(state="cancelled")[0].id == queued.id
    revived.shutdown()


def test_scan_is_resumable_and_records_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "cache"))
    files = _tracks(tmp_path / "music", 6)
    (tmp_path / "music" / "broken.wav").write_bytes(b"not audio")
    (tmp_path / "music" / "notes.txt").write_text("skip me")
    assert len(find_audio(tmp_path / "music")) == 7
    index = LibraryIndex(tmp_path / "index.sqlite")
    events: list[ProgressEvent] = []
    first = scan_library(tmp_path / "music", index, workers=2, batch=3, progress=events.append)
    assert (first.found, first.analyzed, first.failed) == (7, 6, 1)
    assert "broken.wav" in next(iter(first.errors))
    assert events[-1].fraction == 1 and [e.fraction for e in events] == sorted(
        e.fraction for e in events
    )
    stats = index.stats()
    assert (stats.tracks, stats.failures) == (6, 1)
    row = index.search(limit=1)[0]
    assert row.bpm and row.lufs is not None and row.energy_mean is not None and row.camelot
    again = scan_library(tmp_path / "music", index, workers=2)
    assert (again.analyzed, again.skipped, again.failed) == (0, 6, 1)  # broken retried, still bad
    # Changed file content is re-analysed; a copy under another name shares the hash row.
    audio, _ = generate_track(bpm=111, bars=2, seed=99)
    write_audio(files[0], audio)
    (tmp_path / "music" / "copy.wav").write_bytes(files[1].read_bytes())
    third = scan_library(tmp_path / "music", index, workers=1)
    assert third.analyzed == 2
    copy_hash = index.search(q="copy.wav")[0].hash
    assert len((index.get(copy_hash) or row).paths) == 2
    assert index.search(q="100%_") == []
    assert index.search(camelot=row.camelot.lower())


def test_scan_cancel_commits_finished_batches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mixconsole.progress import Cancelled

    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "cache"))
    _tracks(tmp_path / "music", 6)
    index = LibraryIndex(tmp_path / "index.sqlite")
    token = CancelToken()

    def cancel_after_first_batch(event: ProgressEvent) -> None:
        if event.stage == "scan" and 0 < event.fraction < 1:
            token.cancel()

    with pytest.raises(Cancelled):
        scan_library(
            tmp_path / "music",
            index,
            workers=1,
            batch=2,
            progress=cancel_after_first_batch,
            cancel=token,
        )
    assert 1 <= index.stats().tracks < 6
    resumed = scan_library(tmp_path / "music", index, workers=1)
    assert resumed.analyzed + resumed.skipped == 6 and resumed.skipped >= 1


_KILLABLE = """
import sys
from pathlib import Path
from mixconsole.store.library import LibraryIndex, scan_library
scan_library(Path(sys.argv[1]), LibraryIndex(Path(sys.argv[2])), workers=1, batch=2)
"""


def _kill_and_resume(tmp_path: Path, count: int, kill_at: int) -> None:
    import os

    env = {**os.environ, "MIXCONSOLE_CACHE_DIR": str(tmp_path / "cache"), "MIXCONSOLE_WORKERS": "1"}
    music, db = tmp_path / "music", tmp_path / "index.sqlite"
    _tracks(music, count)
    process = subprocess.Popen([sys.executable, "-c", _KILLABLE, str(music), str(db)], env=env)
    index = LibraryIndex(db)
    deadline = time.time() + 120
    try:
        while time.time() < deadline and process.poll() is None:
            if db.exists() and index.stats().tracks >= kill_at:
                break
            time.sleep(0.05)
    finally:
        process.kill()
        process.wait()
    survived = index.stats().tracks
    assert kill_at <= survived < count, "the scan finished before it could be killed"
    stamps = {t.hash: t.analyzed_at for t in index.search(limit=count)}
    os.environ["MIXCONSOLE_CACHE_DIR"] = env["MIXCONSOLE_CACHE_DIR"]
    resumed = scan_library(music, index, workers=2)
    assert resumed.skipped == survived and resumed.analyzed == count - survived
    assert index.stats().tracks == count
    after = {t.hash: t.analyzed_at for t in index.search(limit=count)}
    assert all(after[h] == s for h, s in stamps.items()), "finished tracks were re-analysed"


def test_kill_mid_scan_then_resume_small(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "cache"))
    _kill_and_resume(tmp_path, count=14, kill_at=2)


@pytest.mark.slow
def test_kill_mid_scan_then_resume_100_tracks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "cache"))
    _kill_and_resume(tmp_path, count=100, kill_at=20)
