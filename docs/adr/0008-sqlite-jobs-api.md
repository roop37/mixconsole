# 0008: SQLite schema, job queue and API design (M4.5)

Status: Accepted (supersedes the "deferred" notes in 0003 and 0004).

## Context

The console needs persistent projects, a library over thousands of tracks, a job history that
survives restarts, and an HTTP surface that adds no engine logic of its own.

## Decision

- **Three SQLite files, no ORM.** `index.sqlite` (library), `jobs.sqlite`, and one
  `project.sqlite` per project. Each call opens a short-lived connection (WAL, busy timeout
  30 s, write transactions `BEGIN IMMEDIATE`); schema changes are numbered scripts applied in
  order and recorded in `PRAGMA user_version` (a database newer than the code is refused).
- **Content hash is the identity.** Library and project tracks are keyed by the SHA-256 of the
  file bytes; paths are attributes (many paths per hash in the library). Large arrays stay in
  the existing NPZ analysis files; the database holds queryable summaries and references.
- **MixScript history is append-only**, enforced by triggers that abort `UPDATE`/`DELETE`;
  `seq` orders versions, `parent_id` records ancestry for undo and diff.
- **Jobs run as threads in the server process** that call the service facade (which already
  owns the process pool for analysis). A dispatcher admits queued jobs while the sum of their
  RAM estimates fits the budget. Rows left `queued`/`running` by a crash are marked `failed`
  ("interrupted by server restart") on the next start; nothing is silently resumed, because a
  render is cheap to re-request and half-written artifacts are worse than a visible failure.
- **Progress is polled from the database** by the SSE handler instead of an in-memory fan-out,
  so history replay, `Last-Event-ID` and multiple viewers need no extra machinery.
- **Library scan resumes by skipping**, not by a persisted queue: a file is up to date when its
  path, size, mtime and backend versions match the index; results are committed per batch.
- **API contract.** FastAPI response models are the Pydantic models; the OpenAPI document is
  committed and TypeScript types are emitted by `scripts/gen_api_types.py`, which `check.sh`
  and CI run in `--check` mode (Python emitter chosen over a Node toolchain so the drift check
  needs no extra runtime). Security: loopback bind, Host check, per-run random token (0600
  file), compare in constant time, no CORS unless `--cors-origin` is given.

## Consequences

Single-writer SQLite is ample for one local user; a multi-user or remote deployment would need
a different store. Job threads share the server's memory, so a native crash takes the server
down (history is intact on restart). The RAM estimates are heuristics, not measurements.
`/docs` and `/openapi.json` are served without the token (they contain no user data).
