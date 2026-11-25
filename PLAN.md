# MixConsole — Plan

> Local-first, open-source engine that turns two (then many) songs into a DJ-quality continuous mix,
> and shows you *why* each transition sounds the way it does, so you can change it.

Status: pre-alpha. M0, M1 and M1H provide the foundation, analysis and hardening; later sections describe targets (see ROADMAP.md).

---

## 1. Why this exists

Apple Music AutoMix provides automatic transitions for Apple Music subscription
content on supported devices. MixConsole targets inspectable, editable plans for
local files. This is product motivation, not evidence of listener preference or
comparative quality. See [Apple's supported-content documentation](https://support.apple.com/en-gb/105067).

Prior work informs the design; descriptions below are literature context, not a comparative benchmark:

| Prior art | What it is | Gap MixConsole fills |
|---|---|---|
| [VertexSelection/automix-engine](https://github.com/VertexSelection/automix-engine) (LGPL-2.1) | Stem-aware automatic transitions described in its README; no implementation code reused | Library + CLI + UI; several transition families; candidate search and ranking; editable spec; evaluation suite; multi-track sets |
| [Mixxx Auto DJ](https://manual.mixxx.org/2.5/en/chapters/djing_with_mixxx#auto-dj) | OSS DJ app with Auto DJ transition controls | Musical decisions (phrase, vocals, stems) |
| [DJtransGAN](https://github.com/ChenPaulYu/DJtransGAN) (ICASSP 2022, MIT) | Learns EQ/fade curves from real DJ mixes | Research code; one piece of the pipeline |
| Drum & Bass Auto-DJ (Vande Veire & De Bie 2018, AGPL) | Full auto-DJ for one genre | Genre-locked, old stack |
| [Mosaikbox (Sowula & Knees, ISMIR 2024)](https://robert.sowula.at/publications/ismir-paper/) | Rule-based stem removal + precise beat grid; listening tests showed significant improvement | Paper; we adopt the idea and test it |
| djay Automix / Offtrack / Apple AutoMix | Commercial | Closed; our quality benchmark |

**Positioning goal (not a measured quality claim):** "The open, inspectable AutoMix for your own files." Not "perfect"; *measurably better than a
crossfade and competitive with Apple/djay on blind tests*, plus things they can't do: local files, edits,
explanations, reproducible transition files.

**Honesty rule for all docs/README:** never claim "better than Apple" without a published blind-test result.

## 2. Product principles

1. **Local-first, offline.** Runs on a laptop (target: Apple M-series 16 GB, also Linux/Windows CPU and CUDA). No upload.
2. **Do no harm.** A bad blend is worse than a clean cut. Every transition family has a fallback, and "no transition"
   (gapless album playback, live albums, classical) is a valid choice.
3. **Explainable.** Every decision is written into a human-readable plan (why this cue, why this length, what was rejected).
4. **Editable and reproducible.** The transition is data (a versioned **MixScript** JSON). Same input + same MixScript = bit-identical render.
5. **Pluggable models.** Each analysis step has a backend interface; neural models are optional upgrades with a
   classic DSP fallback, so the core installs in seconds and runs without a GPU.
6. **Measured, not vibes.** Objective metrics on every render + a blind listening harness before any quality claim.
7. **License-clean.** Every model and weight's license recorded in `THIRD_PARTY.md`; non-commercial weights never become a default.

## 3. Architecture

```
 audio files ──► [1 Analyze] ──► TrackAnalysis (cached, content-hash keyed)
                                     │
 pair / playlist ──► [2 Plan] ──► candidates (N MixScripts) ──► [3 Score/Rank] ──► chosen MixScript
                                                                     │
                                         [4 Render] ◄────────────────┘   (deterministic DSP graph)
                                              │
                                         [5 Verify] ─► metrics + report.json + report.html
                                              │ fail → next candidate / fallback family
                                              ▼
                                        mix.wav / mix.flac + MixScript + report
```

### 3.1 Analyze (per track, cached)
| Feature | Default backend (license) | Fallback | Notes |
|---|---|---|---|
| Decode/resample | SoundFile/scipy with external ffmpeg fallback | — | 44.1 kHz float32 internal |
| Beats + downbeats | In-house tracker with librosa onset features | Beat This! optional (MIT code + user-supplied weights) | Beat This! uses CPU inference and omits DBN post-processing. |
| Tempo map | from beats (variable tempo supported) | — | Future planner will reject unsuitable live/rubato beatmatching |
| Bars + phrases | downbeats → 4/8/16-bar phrase grid with novelty-curve alignment | — | phrase = the unit of every cue |
| Sections | In-house novelty + bar-grid boundaries | — | `allin1` is a reserved stub that falls back; upstream NATTEN/madmom need separate review |
| Cue proposals (future) | CUE-DETR or in-house rules | — | Current analysis supplies edge estimates, sections and phrase starts only |
| Key | in-house CQT chroma + key profiles (Krumhansl/Temperley/EDMA) | — | avoid Essentia (AGPL) and libKeyFinder (GPL) in core |
| Loudness/energy | In-house BS.1770 block gating using pyloudnorm K-weighting filters; short-term LUFS and per-bar energy | — | Backend name remains `pyloudnorm`; cross-checked against its meter |
| Vocal activity (M3 target; currently null) | from vocal stem energy + voicing; lyric-gap detection | spectral heuristic | |
| Stems (M3 target) | **Demucs htdemucs** (MIT) on the intro/outro windows only (~60 s each) | none (stem-free families) | RoFormer models optional; weights often CC-BY-NC-SA → never default |
| Silence/edges | head/tail silence, fade-in/out detection, "hard ending" detection | — | |

All analysis is stored as `TrackAnalysis` (JSON + `.npz` arrays) under `~/.cache/mixconsole/<sha256>/<backend>@<version>/`.
Cache keys include PCM identity, backend/pipeline and numerical dependency versions,
and optional checkpoint hashes. File-hash changes recheck PCM identity; corrupt
entries or explicit cache bypass also trigger analysis.

### 3.2 Plan: candidate generation
For a pair (A → B), enumerate:
- **Exit cues** in A (phrase starts in last ~40 %, preferring outro/breakdown) × **entry cues** in B (first ~40 %, intro/first-drop).
- **Lengths:** 0 (cut), 1, 2, 4, 8, 16, 32 bars.
- **Families** (each a parameterised template):
  1. `gapless`: no transition (album continuity, already-segued tracks)
  2. `trim_crossfade`: trim silence + short equal-power fade (safe fallback, any genre)
  3. `cut_on_downbeat`: hard cut on A's phrase end onto B's downbeat (rock, hip-hop)
  4. `beatmatch_blend`: tempo ramp + 3-band EQ crossfade (bass swap at a downbeat)
  5. `stem_handoff`: drums/bass/other/vocals hand over at different bars (Mosaikbox-style removal of clashing stems)
  6. `filter_sweep`: HPF out A / LPF in B
  7. `echo_out`: beat-synced delay tail on A, B enters on the downbeat (great for tempo/key clashes)
  8. `vocal_over_instrumental`: A's acapella over B's intro (only if key-compatible and vocal-safe)
- **Tempo strategy:** none, meet-in-middle, ramp B to A then back (≤ 2 bars per % change), or no-sync if |Δ| > max stretch (default 8 %; half/double-time considered).
- **Key strategy:** none, or pitch-shift by ±1 semitone only when stems are separated and the user allows it ("creative" style).

Hard constraints prune candidates: phrase-aligned, no lead-vocal overlap, no two basslines together,
stretch within limits, no lyric cut mid-word (vocal-gap ≥ 300 ms at exit), loudness within ±1.5 LU across the seam.

### 3.3 Score / Rank
- **v1 heuristic scorer:** weighted features (beat-phase error, key distance on Camelot wheel, energy continuity,
  vocal overlap, bass clash, stretch amount, section-type match, family-genre prior, transition-length fit to tempo).
  Weights live in a YAML file; every score is broken down in the report.
- **v2 learned ranker:** pairwise preference model (LightGBM, then a small MLP over features + audio embeddings, e.g.
  MERT/CLAP if licenses allow) trained from listening-test votes collected by the console's A/B tool. Evaluated on
  *held-out song pairs*.
- **v3 learned curves:** DJtransGAN-style prediction of EQ/fader curves; training labels from real DJ mixes via
  mix-to-track alignment (Kim et al. 2020) + convex fader/EQ estimation (Koo et al. 2022). Research track only.

Styles: `auto` (default), `smooth` (preserve songs, short blends), `club` (long beatmatched/stem blends), `creative` (echo, pitch, acapella).

### 3.4 Render (deterministic DSP graph)
MixScript is compiled into a graph: per-track/per-stem **gain automation**, **3-band DJ EQ** (Linkwitz-Riley isolator),
**HPF/LPF** with resonance, **delay/echo** with beat-synced time, **time-stretch** + optional pitch, **limiter** on the master.
- Time-stretch: **Signalsmith Stretch** (MIT) default; Rubber Band (GPL) optional via subprocess, never linked.
- Automation curves are sample-accurate and smoothed (no zipper noise); stems are re-summed with phase-aligned latency compensation.
- Render only the transition window + copy untouched regions → fast previews (< 2 s per candidate target on M4).
- Output: WAV/FLAC, plus 30 s preview MP3/OGG of each candidate.

### 3.5 Verify (every render)
Re-analyse the rendered seam: beat-phase drift (ms), tempo continuity, short-term loudness curve (max dip/bump in LU),
low-band (< 150 Hz) energy overlap, vocal overlap seconds, clipping/true-peak, spectral flux spikes (clicks).
Thresholds fail a candidate → next candidate → finally `trim_crossfade` as the safe fallback for valid audio. The results go into `report.json` and `report.html`
(waveforms, cue markers, curves, score breakdown, rejected candidates and why).

### 3.6 MixScript (the core contract)
Versioned JSON Schemas (`mixscript/v1` and `mixscript/v1.1`, with deterministic migration): track refs (content hash, not path), in/out points, tempo map, per-stem
automation lanes (time in **beats** of the reference track, not seconds), effects with params, provenance
(analysis backend versions, scorer version, seed). It can be shared without the audio, which makes it copyright-safe and diffable.
The UI edits MixScripts, models output MixScripts, and tests snapshot MixScripts.

### 3.7 Multi-track sets (later)
Pairwise transition-quality matrix (cheap features first, full plan only for top-k) → ordering as an orienteering/TSP
problem with an **energy-arc target** (warm-up → peak → cool-down), key-path smoothness, artist/genre variety,
and user pins ("start with X", "keep album order"). Then plan each transition and render the whole set with a tracklist + cue sheet (CUE file).

## 4. Interfaces

- **Python library** `mixconsole` (typed, documented): `analyze()`, `plan()`, `render()`, `verify()`, `mix()`.
- **CLI** (Typer):
  `mixconsole analyze a.mp3` · `mixconsole mix a.mp3 b.mp3 -o out.wav --style auto --candidates 3` ·
  `mixconsole render plan.mixscript.json` · `mixconsole set ./folder --arc peak -o set.flac` · `mixconsole doctor`
- **Console UI** (local web app): FastAPI backend + Vite/React/TypeScript + wavesurfer.js. Drop files → waveform deck A/B
  with beat/phrase/section/vocal lanes → candidate cards (play, A/B, score breakdown) → drag cue points, edit curves →
  re-render in place → export. Blind A/B voting page feeds the preference dataset (stored locally, export opt-in).
- **Later:** desktop shell (Tauri), real-time playback engine for a "player mode", plugin API for new families/backends.

## 5. Evaluation (how "better" is proven)

1. **Unit + property tests on synthetic audio:** click tracks / generated loops at known BPM, key, phrase length, and
   inserted vocals (TTS/sine bursts) → exact expected cues and zero-drift renders. Run in CI, no models needed.
2. **Analysis accuracy:** beat/downbeat F-measure on a small public set (GTZAN-rhythm, Ballroom, Harmonix sample),
   key accuracy (GiantSteps Key). Run per backend → pick defaults by measurement.
3. **Transition corpus:** 60+ pairs of **Creative Commons** tracks (FMA/Jamendo/ccMixter CC-BY/CC0) across EDM, hip-hop,
   pop, rock, R&B, Bollywood/Indian pop, acoustic, classical; listed in `bench/pairs.yaml` with licenses; never commit audio, fetch script only.
4. **Baselines:** plain 6 s crossfade, trim+crossfade, automix-engine (run as an external process), Mixxx Auto DJ;
   Apple AutoMix/djay by manual recording only for private listening (never redistributed).
5. **Blind listening:** MUSHRA-lite / pairwise A/B in the console; ≥ 10 listeners, randomised, report win-rate with CI.
   Results are published in `bench/results/` with the date and commit.
6. **Performance budget (M4 16 GB):** analysis of a 4-min track ≤ 20 s without stems, ≤ 60 s with stems (MPS);
   plan+render of 3 candidates ≤ 10 s with cache; peak RAM ≤ 4 GB.

## 6. Open-source practice (from Dyad/NOMAD/KeepTrack/Orchestrator learnings)

- Repo: `roop37/mixconsole` (public when M1 is demo-able). Default branch `main`, PRs only, squash merge.
- License: **MIT** (decided 2026-11-25; compatible with MIT/BSD/Apache deps; GPL tools only via subprocess).
  Model weights keep their own licenses, listed in `THIRD_PARTY.md`.
- Docs: README with audio demos (CC music) + 30-second quickstart, CONTRIBUTING (issue-first for features,
  conventional commits, `scripts/check.sh` must pass), CODE_OF_CONDUCT, SECURITY, issue/PR templates (PR body style that
  worked on KeepTrack: what, decisions, files table, tests, screenshots/audio, open questions), CHANGELOG via release-please,
  `AGENTS.md` for AI contributors. **No AI attribution lines in commits or PRs.**
- Tooling: Python 3.12, `uv`, ruff (lint+format), pyright (strict on core), pytest (+ hypothesis), pre-commit;
  GitHub Actions: lint/type/test (fast, model-free) on Linux/macOS + nightly slow job with models; frontend: pnpm, Vite, Biome, Vitest, Playwright smoke.
- Packaging: core wheel (DSP only), optional `[neural]`/`[all]`, placeholder `[stems]`/`[ui]`.
  A public PyPI release is M8. Models currently require local checkpoints; automatic
  checksum-pinned downloads are future work. `mixconsole doctor` reports installed packages.
- Labels: `good first issue`, `transition-family`, `backend`, `bench`. Discussions on for "show your mix".
- Copyright: never commit or ship commercial audio; demos are CC-only with attribution.

## 7. Scalability and frontend architecture (decided 2026-11-18, before the UI exists)

The engine must serve three clients without rewrites: the CLI, the local web console, and later a desktop shell or player.
So the boundaries are fixed now:

```
apps/console (React/TS, M5) ──HTTP+SSE──► mixconsole.server (FastAPI, M4.5)
                                              │  jobs, projects, artifacts
CLI (Typer) ───────────────────────────────► mixconsole.service (pure Python facade)
                                              │  progress callbacks, cancellation
                                         engine: analysis / plan / score / render / verify
                                              │
                                    storage: cache dir + SQLite index + artifact store
```

1. **Service facade** (`mixconsole.service`): the single entry point used by CLI and server. Every long operation takes
   a `Progress` callback (stage, fraction, message) and a `CancelToken`; nothing in the engine prints or reads the CLI.
2. **Jobs**: analysis/render run as jobs (id, state, progress, result ref, error) in a process pool. The CLI runs them
   inline for one worker or in a bounded pool for batches; the future server queues them and streams progress over SSE. Concurrency is bounded by RAM (stems ≈ 2–3 GB each).
3. **Projects**: a project = tracks (hash → original path, user metadata) + analyses + MixScript versions (append-only
   history, enabling undo and diff in the UI) + renders. Stored in `project.sqlite` + artifact folder; portable.
4. **Library index**: SQLite (`index.sqlite`) of every analysed track: hash, path(s), duration, bpm, key, LUFS, energy
   summary, backend versions, and later embeddings. This makes multi-track planning over thousands of tracks a query, not
   a re-scan. Batch analysis = parallel workers + resumable queue.
5. **Frontend artifacts are precomputed by the engine**: multi-resolution waveform peaks (JSON/binary, wavesurfer-compatible),
   beat/bar/phrase/section/vocal lanes, preview encodes (Opus/MP3) served with HTTP range requests.
6. **One contract, generated types**: pydantic models → JSON Schema (`schemas/`) → OpenAPI → generated TypeScript
   types (`packages/schema-ts`). CI fails if generated files drift. The UI never hand-writes API types.
7. **Editability in the contract**: MixScript v1.1 has stable ids for transitions, lanes and effects (points remain ordered), per-transition
   explanation + candidate list, and **user locks** (pinned cue/length/family/lanes the planner must respect on re-plan).
   This is MixScript v1.1 (additive, migration provided) and is delivered before M2 renders depend on it.
8. **Extensibility**: backends register via Python entry points (`mixconsole.backends`);
   `mixconsole.families` is reserved for future planners. Plugins need no engine fork.
9. **Config + models**: `pydantic-settings` config (platformdirs user config path, env `MIXCONSOLE_*`); a future model
   manager downloads weights on demand with sha256 pins, license notice, offline mode and `mixconsole models list|fetch`.
10. **Long audio**: streaming/chunked decode so 1-hour DJ mixes and sets don't need to fit in RAM twice; arrays in `.npz`
    or memory-mapped `.npy`.
11. **Determinism scope**: identical bytes are guaranteed only on the same platform + dependency lock; cross-platform
    golden tests compare with tolerances (sample error < −90 dBFS, cue positions exact).
12. **Repo layout as it grows**: Python engine stays at root (`src/mixconsole`); the web console lives in `apps/console`
    (pnpm workspace); generated TS types in `packages/schema-ts`; docs site in `docs/` (MkDocs Material + mkdocstrings).

## 8. Benchmarks and validation (continuous, not one-off)

| Kind | What | Where | Gate |
|---|---|---|---|
| Perf | time + peak RSS for decode, analysis stages and full analysis at 30 s / 4 min / 10 min; plan, render, verify and 60 min follow when implemented | `mixconsole bench perf`, JSON results with machine fingerprint + git sha | budget table in §5; regressions > 20 % flagged (nightly, non-blocking on shared CI runners) |
| Accuracy (synthetic) | tempo, beats, downbeats, phrases, key, loudness, edges against exact ground truth | `src/mixconsole/bench/accuracy.py` + pytest | blocking in CI |
| Accuracy (public annotations) | beat/downbeat (Ballroom, GTZAN-rhythm annotations), key + tempo (GiantSteps) with user-fetched audio | `bench/datasets/*.yaml` manifests + `mixconsole bench dataset`; user supplies audio and annotations, none committed | reported per backend; future default selection |
| Transition quality | seam metrics on the CC corpus vs baselines | `bench/transitions` (M4) | reported |
| Listening | blind A/B / MUSHRA-lite | console (M5) | published results |
| Docs | README/docs code blocks executed as tests, link check, markdownlint, schema docs generated | CI `docs` job | blocking |
| Supply chain | license allowlist check on the lock (deny GPL/AGPL/NC in core), `pip-audit`, Dependabot, pinned actions | CI | blocking |

M1H measures 30 s / 4 min / 10 min core analysis; 60 min streaming and plan/render/verify
benchmarks await their implementations. Only marked runnable docs blocks are executed.

Results live in `bench/results/<date>-<kind>-<sha>-<machine>.json` plus a generated `bench/results/LATEST.md`.

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Stem separation slow / heavy | only separate ~60 s windows; cache; stem-free families as fallback |
| Model licenses (madmom models, RoFormer weights NC) | backend interface + license registry; defaults MIT/Apache only |
| allin1/NATTEN hard to install on macOS | reserved stub; in-house section default |
| Genre generalisation (CUE-DETR is EDM-trained) | per-genre bench + heuristic cues; family-genre priors |
| "Better than Apple" is unprovable without tests | honesty rule; publish blind tests |
| Scope creep | ROADMAP milestones, each with acceptance tests and a demo |
