# Changelog

## Unreleased

### Added

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
