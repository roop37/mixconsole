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

M4.5 adds the local HTTP API (`mixconsole serve`, see [HTTP API](api.md)): FastAPI over the
service facade, a persistent job queue with SSE progress, portable SQLite projects with
append-only MixScript history, a library index with resumable batch scans, and precomputed UI
artifacts (waveform peaks, lanes, Opus previews served with Range requests). Generated
TypeScript types in `packages/schema-ts` connect the M5 React/Vite console to the same contract.
Streaming long-audio analysis remains a design target.

See the [service decision](adr/0003-service-jobs.md), [SQLite decision](adr/0004-sqlite.md),
[frontend decision](adr/0005-frontend.md) and [API/jobs decision](adr/0008-sqlite-jobs-api.md).
