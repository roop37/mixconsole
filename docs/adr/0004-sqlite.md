# 0004: SQLite projects and library index

Status: Accepted design; implementation deferred to M4.5.

## Context

Thousands of tracks need indexed queries, portable projects and edit history.

## Decision

Use a project SQLite database plus artifacts, append-only MixScript history and a library index. Keep large arrays outside the database.

## Consequences

Schema migrations, resumable queues and concurrent write behavior need tests in M4.5. Current analysis cache is JSON/NPZ plus a file-hash index, not SQLite.
