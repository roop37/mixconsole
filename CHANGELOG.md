# Changelog

## Unreleased

### Changed

- M3.1 stems are opt-in: new `stems` mode `off` (default) | `auto` | `on`
  (`MIXCONSOLE_STEMS`, `mixconsole mix --stems`). `off` disables the stem families
  ("stems disabled") and never separates; `auto` needs a key clash or an unavoidable
  measured vocal collision plus a `stems_auto_margin` (0.05) score win over the best plain
  family; `on` keeps the M3 behaviour. Scorer `heuristic@5`: heuristic-only vocal data
  penalises plain blends only mildly.
- Verification gates stem seams on separation bleed (`stem_leakage`, `max_stem_leakage`
  0.25; None when unmeasured). The gain-repaired re-check now also applies the vocal-overlap
  limit.

### Added

- M4.5 service + API: `mixconsole serve` (FastAPI, 127.0.0.1 + per-run token, Host check, SSE
  job progress, HTTP Range), 35 operations for projects, tracks, analyses, plans/MixScript
  versions (append-only, diff), renders, library and jobs; SQLite projects (`project.sqlite` +
  artifact folder), library index (`index.sqlite`) with `mixconsole library scan` (batch,
  parallel, resumable), persistent RAM-bounded job queue (`jobs.sqlite`), multi-resolution
  audiowaveform peaks (JSON + .dat), lane data and Opus previews. OpenAPI committed with
  generated TypeScript types in `packages/schema-ts` (`scripts/gen_api_types.py`, drift check in
  `check.sh` and CI). New `server` extra (fastapi, uvicorn), `httpx` dev dependency, settings
  `data_dir` and `job_ram_mb`. ADR 0008.
- M4 transition corpus (`bench/pairs.yaml`: 37 CC0/CC-BY tracks, 36 pairs, licence and
  attribution per track, licence re-verified on the track page before download) and
  `mixconsole bench corpus`: plain 6 s crossfade, trim + equal-power crossfade and MixConsole
  `smooth`/`auto`/`club` on every pair with seam metrics, per-system table in `LATEST.md`
  (unmeasured metrics print `n/a`), and optional automix-engine run as an external process
  (`scripts/setup_automix_engine.sh`, own venv in the cache, never imported or vendored).
- `mixconsole listen build` / `listen results`: offline blind A/B + MUSHRA-lite page (hidden
  reference, hard-cut anchor, salted audio tokens, votes saved as local JSON, no network) and
  win rates / means with seeded bootstrap CIs and hidden-reference rater screening.

- M3 optional `stems` extra (Demucs htdemucs, MIT, checksum-pinned weights via
  `mixconsole models fetch htdemucs`), windowed exit/entry stem separation cached per
  PCM hash/window/model on CPU or Apple MPS, and residual-folded stems that re-sum exactly.
- Vocal activity per bar/beat, lyric gaps (>= 300 ms) and stem windows in `TrackAnalysis`
  (additive schema change); spectral heuristic fallback when the extra is absent.
- `stem_handoff` (classic and key-clash `drums_only`) and `vocal_over_instrumental`
  families with a lead-vocal/bass/lyric-gap constraint set, per-stem automation lanes,
  latency-compensated re-summing, and measured vocal/bass overlap in verification.
- Fast tiny-grid accuracy test, xdist test runs and a 91 % coverage floor.

- M2 six transition families, bounded planner, style-weighted scorer and MixScript
  candidate explanations with gain/effect automation.
- Deterministic two-track WAV/FLAC renderer using Signalsmith Stretch, EQ, filters,
  echo and true-peak ceiling; seam verification, fallback and local HTML report.
- `mix`, `plan`, `render` and `bench transitions` CLI commands, three audition
  previews, PCM-hash replay checks and synthetic M2 DSP/round-trip tests.

- M0 package foundation, uv tooling, CI, contributor documents and license (relicensed Apache-2.0 → MIT before first publication, 2026-11-25).
- MixScript v1 models, JSON Schema, example plans and CLI validation.
- Seeded synthetic audio with beat, downbeat, phrase, key and vocal annotations.
- Canonical stereo audio decoding, WAV/FLAC writing and PCM/file hashing.
- Environment diagnostics and version command.

- M1 TrackAnalysis v1 with JSON Schema and compact NPZ feature curves.
- Typed analysis backends: core beat/downbeat tracking, tempo continuity, key profile
  ensemble, LUFS/true-peak estimates, bar energy, phrases, sections and edge cues.
- Optional lazy Beat This! adapter with core fallback and checkpoint provenance;
  reserved All-In-One section adapter stub with documented NATTEN caveat.
- Public `mixconsole.analyze`, rich multi-file CLI, JSON export and cache management.
- Atomic PCM/version-addressed cache, integrity validation, cache bypass and overrides.
- Synthetic analysis acceptance tests and reproducible four-minute benchmark.
- Optional phrase-grid offset in the existing seeded synthetic generator.

- M1R: noise-robust tempo (onset-ACF + metrical choice), in-house tempo-locked beat
  tracker, beat grid through breakdowns, least-squares tempo map, bar-grid sections;
  `tests/test_robustness.py`. Fixes 97 BPM read as ~195 BPM and over-split sections.
- MixScript v1.1: stable ids, per-transition explanation/candidates, locks, play
  regions, namespaced extensions; deterministic v1 → v1.1 upgrade; canonical dumps.
- `mixconsole bench perf|accuracy`, bench-result/v1 schema, LATEST.md, `--compare`.

- M1H service facade with bounded process workers, stage cancellation, progress,
  pydantic-settings TOML/environment configuration and backend entry-point plugins.
- Public dataset hooks for Ballroom, GTZAN-Rhythm and GiantSteps key/tempo.
- Coverage/timeout and runnable docs tests, expanded Ruff rules, schema drift and
  generated third-party license gates; CPU-only optional torch routing under uv.
- Pinned CI jobs for checks, docs, supply chain, wheel builds and CodeQL; nightly
  benchmarks, Dependabot, repository/commit hooks, Material docs and architecture ADRs.
- Frontend contract stubs in apps/console and packages/schema-ts; no UI code.

### Removed

- `scripts/bench_analysis.py` (superseded by `mixconsole bench perf`).

The console UI remains a future milestone.
