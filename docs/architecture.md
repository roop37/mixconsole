# Architecture

The implemented path is local file → decode → cached TrackAnalysis → bounded
transition search → MixScript v1.1 → deterministic render → seam checks and report. Named backends
supply beats, key, loudness, sections and edge cues. JSON holds typed metadata and
NPZ references; integrity hashes detect mismatched or interrupted cache writes.

The CLI calls `mixconsole.service.analyze_tracks`. Its inline path reports stage
progress, and its bounded process pool reports completed tracks in deterministic
input order. Cancellation is signaled to processes at stage checkpoints. Engine
code uses callbacks and stdlib logging, with no terminal printing.

Backend plugins use the `mixconsole.backends` entry-point group. Each entry point
loads a backend object or zero-argument factory with `kind`, `name`, `version` and
the corresponding typed `analyze` method. Built-in names cannot be replaced. Broken
plugins log a warning and are skipped. `mixconsole.families` loads
transition templates through the same entry-point pattern.
Plugins are installed Python code and run with the user's privileges.

M2 uses six stem-free families, a style-weighted heuristic and audio-derived
seam checks. M3 adds optional stems (Demucs windows), vocal activity and the `stem_handoff` and
`vocal_over_instrumental` families.

M4.5 adds FastAPI HTTP endpoints, job state, SSE progress, portable SQLite projects,
append-only MixScript history, a library index and preview artifacts. M5 adds a
React/Vite/TypeScript console. Schema-derived types will connect these clients to
the same service contract. Waveform pyramids, range-served previews and streaming
long-audio analysis are design targets, not M1H deliverables.

See the [service decision](adr/0003-service-jobs.md), [SQLite decision](adr/0004-sqlite.md)
and [frontend decision](adr/0005-frontend.md).
