# MixConsole — Roadmap

One milestone at a time. A milestone is **done** only when `scripts/check.sh` passes and its acceptance list is met with
recorded evidence (logs, rendered audio paths, report.html) in `planning/Mxx-*.md`.

| # | Milestone | Outcome | Acceptance (summary) |
|---|---|---|---|
| M0 | Foundation | Repo skeleton, tooling, CI, docs, MixScript v1 schema, synthetic-audio test kit | `uv sync`, `scripts/check.sh` green; schema validates examples; synthetic generator makes click tracks with known BPM/phrases |
| M1 | Analysis core | `mixconsole analyze` → cached TrackAnalysis (beats, downbeats, tempo map, phrases, key, loudness, energy, silence, sections fallback) | Synthetic: BPM within 0.1, downbeats exact, phrases exact; cache hit < 0.2 s; Beat This! backend behind `[neural]` |
| M1H | Hardening + bench harness | MixScript v1.1 (ids, locks, per-transition explanation/candidates), service facade with progress/cancel, config, entry-point registry, perf + accuracy bench harness, docs validation, supply-chain CI | `mixconsole bench perf|accuracy` writes results + LATEST.md; README code blocks run in tests; license allowlist + pip-audit + link check green; v1→v1.1 migration tested |
| M2 | Two-song mix v0.1 | Planner (families 1–4, 6, 7), heuristic scorer, renderer (gain/EQ/filters/echo/stretch/limiter), verify + fallback, `mixconsole mix a b` | Synthetic pairs: drift < 5 ms, loudness dip < 1.5 LU, no clipping; 3 candidates + report.html; deterministic renders (hash-equal) |
| M3 | Stems + vocals | Demucs windows, vocal activity + lyric gaps, `stem_handoff`, `vocal_over_instrumental`, bass/vocal clash rules | No lead-vocal overlap on test pairs; stems cached per window; works without stems installed |
| M4 | Bench | CC corpus fetch script, baselines (crossfade, automix-engine external), metrics dashboard, analysis-accuracy eval | `bench/run.sh` produces results table + listening pages |
| M4.5 | Service + API | Projects (SQLite), library index, job queue + SSE progress, waveform peaks, preview encodes with range requests, FastAPI + OpenAPI → generated TS types | API contract tests; 100-track batch analysis resumable; TS types drift check in CI |
| M5 | Console UI | Local web app: decks, lanes, candidate audition, cue drag, curve edit, re-render, export, blind A/B voting | Playwright smoke: load 2 files → audition → edit cue → export |
| M6 | Multi-track sets | Transition matrix, energy-arc ordering, set render + CUE sheet, `mixconsole set` | 10-track folder → ordered set with report; user pins respected |
| M7 | Learned ranker | Preference data from A/B tool, LightGBM ranker, held-out pair evaluation | Ranker beats heuristic on held-out pairs (pairwise accuracy, CI reported) |
| M8 | Release 0.1 | PyPI package, docs site, demo audio, public repo, launch post | Fresh-machine install < 2 min; README demos; tagged release |
| R  | Research track | DJtransGAN-style curve model, mix-to-track alignment dataset, real-time player, Tauri desktop | Separate proposals |
