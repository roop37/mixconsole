"""Small SQLite helper: one short-lived connection per call, WAL, versioned migrations.

Every writer (request threads, job threads, scan processes) opens its own connection, so
SQLite's file locking (busy timeout 30 s) is the only coordination needed. Schema changes are
numbered scripts applied in order; ``PRAGMA user_version`` records the applied count.
"""

import sqlite3
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect(
    path: Path, migrations: Sequence[str], *, write: bool = True
) -> Generator[sqlite3.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        migrate(conn, migrations)
        if not write:
            yield conn
            return
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")
    finally:
        conn.close()


def migrate(conn: sqlite3.Connection, migrations: Sequence[str]) -> None:
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if version > len(migrations):
        raise RuntimeError(f"database schema {version} is newer than this MixConsole")
    for number in range(version, len(migrations)):
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Re-check under the write lock: another process may have migrated meanwhile.
            if int(conn.execute("PRAGMA user_version").fetchone()[0]) > number:
                conn.execute("ROLLBACK")
                continue
            for statement in migrations[number].split(";\n"):
                if statement.strip():
                    conn.execute(statement)
            conn.execute(f"PRAGMA user_version={number + 1}")
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
