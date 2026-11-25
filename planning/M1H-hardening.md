# M1H — Hardening and benchmark harness

## Audit recorded before implementation

Audit date: 2026-11-18. The entire M0/M1 tree is uncommitted; no commits,
staging, remote access through git, or resets are part of this milestone.
Read AGENTS.md, PLAN.md (including §§7–8), ROADMAP.md and both prior evidence
files before editing. Baseline `scripts/check.sh` passed: 101 passed, 1 slow
model test deselected. Original logs: `/tmp/m1h-baseline.log`.

Status meanings: **verified** = supported by the cited source/test, including
explicitly historical evidence; **wrong** = contradicted by implementation or
current requirements; **not yet true** = roadmap/design goal, not delivered.
Policy statements are verified as repository requirements, not claims of
implemented future behavior. Historical benchmark numbers are retained as
historical measurements, not current results. Tables below inventory all prose,
list and table claims in the requested documents before implementation; fenced
examples are covered by the separate schema/CLI/code audit. Headings and table
separators carry no independent claims.

### Actionable findings

| Claim | Initial status | Evidence / correction required |
| --- | --- | --- |
| PLAN status “planning”, builder attribution | wrong | M0/M1 exist; remove attribution and identify implemented scope. |
| PLAN §3.1 default Beat This!, ffmpeg via soundfile/audioread | wrong | registry.DEFAULTS uses librosa; io uses SoundFile/scipy + direct ffmpeg subprocess. Distinguish target architecture. |
| PLAN §7 point IDs | wrong | M1H specification requires ordered points, stable transition/lane/effect IDs. Align spec. |
| PLAN config fixed ~/.config on every OS | wrong | platformdirs is platform dependent. |
| PLAN “trim_crossfade always passes” | not yet true | Renderer/verifier are stubs; a target, never a guarantee for arbitrary invalid input. |
| README schema regeneration only v1 | wrong | M1H must freeze v1 and export v1.1, TrackAnalysis and bench schemas. |
| README all unknown/nonfinite data rejected | verified | tests/test_mixscript.py; extension JSON is the deliberate new exception for unknown namespaced data. |
| THIRD_PARTY full lock allowlist compliance | not yet true | NVIDIA EULA packages in optional torch closure violate new allowlist; select CPU torch wheels for Linux. |
| THIRD_PARTY soxr LGPL linkage | not yet true | Need inspect wheel linkage and document shared extension/library boundary. |
| M0/M1 prose describes historical state | verified | Prior evidence retained as dated records, add supersession notes where appropriate. |
| Core no torch/GPU, analysis/caches/CLI | verified | baseline 101 tests including subprocess import guard, synthetic accuracy and cache corruption tests. |
| M2–M8 planner/render/service HTTP/SQLite/UI claims | not yet true | Source stubs + ROADMAP; retain as explicitly future. |

### Document claim inventory

| Source / line | Claim | Initial status | Evidence |
| --- | --- | --- | --- |
| README.md:3 | The open, inspectable AutoMix for your own files. A local-first engine for automatic | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:4 | DJ transitions, with editable, reproducible plans that explain each decision. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:6 | **Status: pre-alpha — M1 Analysis core.** Analyze local tracks for beats, key, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:7 | loudness, bars, phrases, sections and edges, with inspectable JSON + NPZ exports. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:8 | Transition planning, rendering and the console UI are future milestones. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:12 | Install Python 3.12+ and [uv](https://docs.astral.sh/uv/), then from this checkout: | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:25 | SoundFile handles common audio formats. Install `ffmpeg` on your system for other | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:26 | formats and multichannel downmixing (`brew install ffmpeg` on macOS or | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:27 | `sudo apt install ffmpeg` on Ubuntu). It runs as an external process. Audio stays | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:28 | on your machine; the core does not need torch, a GPU, or downloaded model weights. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:29 | The `neural` extra adds Beat This! and torch; `all` includes `neural`. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:30 | The `stems` and `ui` extras remain placeholders. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:50 | Internal audio is float32 stereo at 44.1 kHz. WAV output preserves float samples; | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:51 | FLAC uses PCM24 and quantizes them. PCM identity hashes canonical little-endian | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:52 | decoded samples; file identity hashes the original file bytes. Repeated I/O and | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:53 | synthesis are deterministic with the same inputs and software environment. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:54 | Codec/library versions may change decoded PCM across environments. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:58 | [`TrackAnalysis`](schemas/track-analysis-v1.json) stores file and canonical PCM hashes, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:59 | seconds-based timestamps, zero-based bar indices, tempo segments, top key alternatives, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:60 | structure and edge estimates, backend versions and analysis seed (zero). Tonic uses | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:61 | pitch classes C=0 through B=11; mode is major/minor. Meter is 3 or 4 quarter notes. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:62 | Phrase lengths are 4/8/16 bars; a final phrase/bar may be truncated at EOF. Section | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:63 | labels and vocal activity are null in M1. Key estimates on silence have low confidence; | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:64 | beatless signals have no BPM or bars. Synthetic results do not establish real-music accuracy. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:66 | `result.arrays["short_term_lufs"]` is a 10 Hz curve of forward-looking 3 s K-weighted | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:67 | windows, padded with silence at EOF. Silence uses a -120 LUFS floor in this numeric | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:68 | array; integrated loudness and peak are null for digital silence. True peak uses | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:69 | 4x polyphase oversampling and is an estimate, not a certified BS.1770 meter. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:70 | `result.arrays["bar_energy"]` has columns RMS, onset strength, low (<150 Hz), mid | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:71 | (150–2000 Hz), and high (>2000 Hz). Band energy uses the shared 11.025 kHz analysis | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:72 | spectrum, so the high band ends at 5512.5 Hz. Spectral energies are relative STFT | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:73 | power, not calibrated loudness. JSON has typed NPZ references (key, shape, columns); | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:74 | `save_analysis`/`load_analysis` write and hydrate the sibling NPZ with an integrity hash. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:75 | Single-file CLI export writes an object; multi-file export writes an array plus | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:76 | numbered individual JSON/NPZ pairs. Keep the NPZ siblings with exported JSON. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:78 | The defaults are `librosa` beats, in-house `profiles` key estimation, `pyloudnorm` | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:79 | loudness, in-house `novelty` sections and `edges` cues. Beat tracking combines an | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:80 | onset envelope, 70–180 BPM prior and half/double resolution, librosa dynamic | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:81 | programming, transient refinement, accent/low-band/harmonic bar phase (3/4 or 4/4), | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:82 | and smoothed tempo segments. Key scoring ensembles Krumhansl–Kessler, Temperley | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:83 | and an original EDMA-style triadic profile. Phrases align 4/8/16-bar grids to changes | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:84 | in energy, harmonic novelty and broadband attacks. These are estimates; uncertain | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:85 | or atypical meter/tempo, rubato and percussion-free music need later corpus evaluation. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:87 | Select backends with `analyze(path, backends={"beats": "beat_this"})` or | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:88 | `mixconsole analyze song.wav --beats beat_this`. Install `uv sync --extra neural` | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:89 | and set `MIXCONSOLE_BEAT_THIS_CHECKPOINT` to a local, trusted official MIT checkpoint. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:90 | The adapter hashes the checkpoint into cache provenance, uses CPU inference with a | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:91 | fixed seed and disables DBN processing. It does not download weights automatically. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:92 | Unavailable packages/checkpoints or optional runtime failures log a warning and | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:93 | fall back; unknown backend names fail clearly. See the | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:94 | [official Beat This! model instructions](https://github.com/CPJKU/beat_this#available-models). | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:96 | `--sections allin1` reserves an optional **stub** and falls back to novelty. It is not | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:97 | installed by any extra: All-In-One needs a compatible NATTEN build and its upstream | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:98 | pipeline has madmom dependencies. NATTEN support/build requirements vary by torch, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:99 | CUDA and platform, particularly on macOS. See the | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:100 | [upstream installation notes](https://github.com/mir-aidj/all-in-one#installation). | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:101 | No madmom code or models are used by MixConsole. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:103 | Cache entries live under `~/.cache/mixconsole/<pcm_sha256>/<backend>@<version-key>/`. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:104 | The version key fingerprints all selected backend versions, numerical dependency | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:105 | versions and optional checkpoint content. An auxiliary file-hash index avoids | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:106 | re-decoding on hits; changing file bytes rechecks PCM identity. JSON and NPZ writes | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:107 | are atomic, and their hash pairing detects interrupted writes. Corrupt entries are | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:108 | recomputed. `MIXCONSOLE_CACHE_DIR`, `cache_dir=...` or CLI `--cache-dir` override the | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:109 | root. `use_cache=False` / `--no-cache` bypass all cache reads and writes; explicit | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:110 | JSON export still writes its requested files. `mixconsole cache info` reports entry | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:111 | count/bytes; `mixconsole cache clear` removes recognized analysis entries and the | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:112 | file-hash index while preserving unrelated files. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:114 | `uv run python scripts/bench_analysis.py` measures a four-minute generated track, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:115 | first analysis, warm recomputation and a cache hit. Fast tests reuse session fixtures; | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:116 | `uv run pytest -m slow` runs optional Beat This! inference when its package and local | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:117 | checkpoint are present. It skips with a reason otherwise. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:121 | The [schema](schemas/mixscript-v1.json) and [examples](examples/) describe tracks by | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:122 | PCM SHA-256 rather than paths. Examples contain invented hashes and no music. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:123 | `uv run python scripts/gen_schema.py` regenerates the committed schema. | wrong | see actionable findings above |
| README.md:125 | Track IDs are keys in `tracks`; transitions reference these IDs. `duration` and cue | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:126 | `seconds` use seconds. Cue `beat` positions are zero-based source quarter notes. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:127 | Automation and tempo-map beats are relative to the transition start on | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:128 | `tempo.reference_track`'s quarter-note grid. Tempo interpolates linearly in beat | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:129 | position between map points; an empty map records intent only. `beats_per_bar` | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:130 | specifies quarter notes per reference bar. Gain and delay send use linear amplitude, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:131 | EQ uses dB, and filter frequencies use Hz. A point's curve controls the segment to | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:132 | the next point. Effect parameters are named scalars; no effects execute in M0. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:133 | Stem/pitch strategies describe intent; feasibility checks belong to later planners. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:135 | Pydantic validation also checks track references, cue bounds, ordering and lane | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:136 | uniqueness. JSON Schema expresses structural constraints; use `mixconsole validate` | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:137 | for the full contract. Unknown fields and non-finite numbers are rejected. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:141 | See [ROADMAP.md](ROADMAP.md) for milestones, [PLAN.md](PLAN.md) for architecture, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:142 | and [CONTRIBUTING.md](CONTRIBUTING.md) for development practices. Milestone evidence | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:143 | is in [planning/M0-foundation.md](planning/M0-foundation.md) and | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:144 | [planning/M1-analysis.md](planning/M1-analysis.md). | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:146 | **Honesty:** DJ-quality transitions are the goal, not an M1 capability. There are no | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:147 | published listening results yet. We make no claim of outperforming Apple AutoMix, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:148 | djay, or any other system without published blind listening tests. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:150 | Licensed under [Apache-2.0](LICENSE). Dependencies retain their own licenses; | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| README.md:151 | see [THIRD_PARTY.md](THIRD_PARTY.md). Do not contribute commercial audio or weights. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| CONTRIBUTING.md:3 | Open an issue before implementing a feature so its milestone, scope and acceptance | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:4 | criteria can be agreed. Small bug fixes can go directly to a pull request. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:5 | Read [PLAN.md](PLAN.md), [ROADMAP.md](ROADMAP.md), and [AGENTS.md](AGENTS.md) first. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:15 | The core must work without torch or a GPU. Keep work within the assigned milestone | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:16 | and record commands, results and artifact paths in `planning/Mxx-*.md`. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:17 | Before submitting, run `scripts/check.sh`: ruff, format check, strict core pyright, | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:18 | and `pytest -m "not slow"`. Optional slow/model tests use `uv run pytest -m slow`. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:19 | When the contract changes, regenerate `schemas/mixscript-v1.json` with | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:20 | `uv run python scripts/gen_schema.py` and update the examples and tests. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:22 | Use conventional commits such as `feat(analysis): add beat cache`, | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:23 | `fix(render): smooth gain ramp`, `test: cover silence`, `docs: explain timing`, or | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:24 | `chore: update tooling`. Keep commits and PRs focused on the final change. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:28 | Never copy code from GPL/LGPL/AGPL projects, including automix-engine, Rubber Band, | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:29 | Essentia, madmom models, and libKeyFinder. Papers and documentation may inform an | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:30 | original implementation. GPL tools may only be optional external-process backends. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:31 | Record every new dependency or model weight with its license and URL in | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:32 | `THIRD_PARTY.md`; non-commercial weights must never be defaults. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:34 | Seed randomness. Identical inputs and MixScripts must produce identical rendered | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:35 | bytes in the same supported environment. Never commit model weights or audio other | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:36 | than tiny synthetic fixtures generated by code. Prefer generating fixtures in | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:37 | pytest temporary directories; do not attach copyrighted tracks to issues or PRs. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:41 | Use the repository template with these sections: | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:43 | - **What** — the problem and resulting behavior. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:44 | - **Decisions** — relevant tradeoffs and scope. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:45 | - **Files** — key changed paths and their roles. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:46 | - **Tests** — commands, results, and milestone evidence. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:47 | - **Audio-or-screenshots** — licensed demos or synthetic evidence when relevant. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:48 | - **Open questions** — unresolved decisions, or “None”. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:50 | By contributing, you agree that your contributions are licensed under Apache-2.0 | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| CONTRIBUTING.md:51 | and that you will follow the [Code of Conduct](CODE_OF_CONDUCT.md). | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| AGENTS.md:3 | Read `PLAN.md` (architecture, principles) and `ROADMAP.md` (milestones) before changing anything. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| AGENTS.md:6 | - Work only on the milestone you were given. Record evidence in `planning/Mxx-*.md` (commands run, results, paths). | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| AGENTS.md:7 | - `scripts/check.sh` must pass before you finish (ruff, ruff format --check, pyright, pytest -m "not slow"). | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| AGENTS.md:8 | - **Clean-room:** never copy code from GPL/LGPL/AGPL projects (e.g. VertexSelection/automix-engine, Rubber Band, Essentia, | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| AGENTS.md:9 |   madmom models, libKeyFinder). Reading papers and docs is fine. GPL tools may only be called as external processes, behind an optional backend. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| AGENTS.md:10 | - Every new dependency or model weight → add it to `THIRD_PARTY.md` with license + URL. No non-commercial weights as defaults. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| AGENTS.md:11 | - Never commit audio except tiny synthetic fixtures generated by code. Never commit model weights. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| AGENTS.md:12 | - No AI attribution in commits, PRs or files (no Co-Authored-By, no "Generated with ..."). | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| AGENTS.md:13 | - Conventional commits: `feat(analysis): ...`, `fix(render): ...`, `test: ...`, `docs: ...`, `chore: ...`. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| AGENTS.md:14 | - Determinism: seed everything; same input + MixScript ⇒ identical output bytes. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| AGENTS.md:15 | - Core package (`mixconsole` without extras) must import and run with no torch / no GPU. | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| AGENTS.md:36 | - Setup: `uv sync --all-extras --dev` (or `uv sync --dev` for core only) | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| AGENTS.md:37 | - Check: `scripts/check.sh` | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| AGENTS.md:38 | - Slow/model tests: `uv run pytest -m slow` | verified | repository policy; pyproject.toml, scripts/check.sh, source layout |
| PLAN.md:3 | > Local-first, open-source engine that turns two (then many) songs into a DJ-quality continuous mix, | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:4 | > and shows you *why* each transition sounds the way it does, so you can change it. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:6 | Status: planning (2026-11-18). Owner: roop37. Builder: milestone implementation, milestone by milestone (see ROADMAP.md). | wrong | see actionable findings above |
| PLAN.md:12 | Apple Music AutoMix (iOS 26) proved people want "DJ-style" transitions without a DJ: beatmatching, | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:13 | time-stretching, silence trimming, and choosing *not* to blend when a pair doesn't suit it. It is closed, | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:14 | works only on Apple Music catalogue streams (not uploaded/purchased files), exposes no public API, and | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:15 | can't be edited. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:17 | Prior open work exists but is either research code, a single hard-coded script, genre-locked, or old: | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:19 | / Prior art / What it is / Gap MixConsole fills / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:21 | / [VertexSelection/automix-engine](https://github.com/VertexSelection/automix-engine) (LGPL-2.1, 2026-08) / One 136 KB script: CUE-DETR cues + Demucs stems + Rubber Band `--fine`; fixed 32-beat handoff; vocal-gap waiting; drift rejection; JSON report; expects `song1.mp3`/`song2.mp3` / Library + CLI + UI; several transition families; candidate search and ranking; editable spec; evaluation suite; multi-track sets / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:22 | / [Mixxx Auto DJ](https://manual.mixxx.org/2.5/en/chapters/djing_with_mixxx#auto-dj) / Mature OSS DJ app; Auto DJ is mostly crossfade-by-time / Musical decisions (phrase, vocals, stems) / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:23 | / [DJtransGAN](https://github.com/ChenPaulYu/DJtransGAN) (ICASSP 2022, MIT) / Learns EQ/fade curves from real DJ mixes / Research code; one piece of the pipeline / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:24 | / Drum & Bass Auto-DJ (Vande Veire & De Bie 2018, AGPL) / Full auto-DJ for one genre / Genre-locked, old stack / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:25 | / Mosaikbox (Sowula & Knees, ISMIR 2024) / Rule-based stem removal + precise beat grid; listening tests showed significant improvement / Paper; we adopt the idea and test it / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:26 | / djay Automix / Offtrack / Apple AutoMix / Commercial / Closed; our quality benchmark / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:28 | **Positioning:** "The open, inspectable AutoMix for your own files." Not "perfect"; *measurably better than a | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:29 | crossfade and competitive with Apple/djay on blind tests*, plus things they can't do: local files, edits, | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:30 | explanations, reproducible transition files. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:32 | **Honesty rule for all docs/README:** never claim "better than Apple" without a published blind-test result. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:36 | 1. **Local-first, offline.** Runs on a laptop (target: Apple M-series 16 GB, also Linux/Windows CPU and CUDA). No upload. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:37 | 2. **Do no harm.** A bad blend is worse than a clean cut. Every transition family has a fallback, and "no transition" | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:38 |    (gapless album playback, live albums, classical) is a valid choice. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:39 | 3. **Explainable.** Every decision is written into a human-readable plan (why this cue, why this length, what was rejected). | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:40 | 4. **Editable and reproducible.** The transition is data (a versioned **MixScript** JSON). Same input + same MixScript = bit-identical render. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:41 | 5. **Pluggable models.** Each analysis step has a backend interface; neural models are optional upgrades with a | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:42 |    classic DSP fallback, so the core installs in seconds and runs without a GPU. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:43 | 6. **Measured, not vibes.** Objective metrics on every render + a blind listening harness before any quality claim. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:44 | 7. **License-clean.** Every model and weight's license recorded in `THIRD_PARTY.md`; non-commercial weights never become a default. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:62 | / Feature / Default backend (license) / Fallback / Notes / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:64 | / Decode/resample / ffmpeg via `soundfile`/`audioread` / — / 44.1 kHz float32 internal / | wrong | see actionable findings above |
| PLAN.md:65 | / Beats + downbeats / **Beat This!** (MIT code + weights) / librosa beat track / Beat This! drops DBN post-processing; we add our own tempo-continuity smoothing + a confidence score / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:66 | / Tempo map / from beats (variable tempo supported) / — / flags live/rubato tracks as "unmixable by beatmatch" / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:67 | / Bars + phrases / downbeats → 4/8/16-bar phrase grid with novelty-curve alignment / — / phrase = the unit of every cue / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:68 | / Sections / **All-In-One** (allin1, MIT) optional / self-similarity novelty (in-house) / allin1 needs NATTEN/madmom; keep optional extra / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:69 | / Cue proposals / **CUE-DETR** (MIT) optional / in-house rules (energy rise, section starts, phrase starts) / CUE-DETR is EDM-trained → evaluate per genre / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:70 | / Key / in-house CQT chroma + key profiles (Krumhansl/Temperley/EDMA) / — / avoid Essentia (AGPL) and libKeyFinder (GPL) in core / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:71 | / Loudness/energy / **pyloudnorm** (MIT) EBU R128 integrated + short-term; RMS/onset energy per bar / — / / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:72 | / Vocal activity / from vocal stem energy + voicing; lyric-gap detection / spectral heuristic / / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:73 | / Stems / **Demucs htdemucs** (MIT) on the intro/outro windows only (~60 s each) / none (stem-free families) / RoFormer models optional; weights often CC-BY-NC-SA → never default / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:74 | / Silence/edges / head/tail silence, fade-in/out detection, "hard ending" detection / — / / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:76 | All analysis is stored as `TrackAnalysis` (JSON + `.npz` arrays) under `~/.cache/mixconsole/<sha256>/<backend>@<version>/`. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:77 | Re-analysis happens only when the file hash or backend version changes. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:80 | For a pair (A → B), enumerate: | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:81 | - **Exit cues** in A (phrase starts in last ~40 %, preferring outro/breakdown) × **entry cues** in B (first ~40 %, intro/first-drop). | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:82 | - **Lengths:** 0 (cut), 1, 2, 4, 8, 16, 32 bars. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:83 | - **Families** (each a parameterised template): | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:84 |   1. `gapless`: no transition (album continuity, already-segued tracks) | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:85 |   2. `trim_crossfade`: trim silence + short equal-power fade (safe fallback, any genre) | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:86 |   3. `cut_on_downbeat`: hard cut on A's phrase end onto B's downbeat (rock, hip-hop) | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:87 |   4. `beatmatch_blend`: tempo ramp + 3-band EQ crossfade (bass swap at a downbeat) | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:88 |   5. `stem_handoff`: drums/bass/other/vocals hand over at different bars (Mosaikbox-style removal of clashing stems) | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:89 |   6. `filter_sweep`: HPF out A / LPF in B | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:90 |   7. `echo_out`: beat-synced delay tail on A, B enters on the downbeat (great for tempo/key clashes) | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:91 |   8. `vocal_over_instrumental`: A's acapella over B's intro (only if key-compatible and vocal-safe) | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:92 | - **Tempo strategy:** none, meet-in-middle, ramp B to A then back (≤ 2 bars per % change), or no-sync if /Δ/ > max stretch (default 8 %; half/double-time considered). | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:93 | - **Key strategy:** none, or pitch-shift by ±1 semitone only when stems are separated and the user allows it ("creative" style). | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:95 | Hard constraints prune candidates: phrase-aligned, no lead-vocal overlap, no two basslines together, | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:96 | stretch within limits, no lyric cut mid-word (vocal-gap ≥ 300 ms at exit), loudness within ±1.5 LU across the seam. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:99 | - **v1 heuristic scorer:** weighted features (beat-phase error, key distance on Camelot wheel, energy continuity, | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:100 |   vocal overlap, bass clash, stretch amount, section-type match, family-genre prior, transition-length fit to tempo). | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:101 |   Weights live in a YAML file; every score is broken down in the report. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:102 | - **v2 learned ranker:** pairwise preference model (LightGBM, then a small MLP over features + audio embeddings, e.g. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:103 |   MERT/CLAP if licenses allow) trained from listening-test votes collected by the console's A/B tool. Evaluated on | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:104 |   *held-out song pairs*. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:105 | - **v3 learned curves:** DJtransGAN-style prediction of EQ/fader curves; training labels from real DJ mixes via | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:106 |   mix-to-track alignment (Kim et al. 2020) + convex fader/EQ estimation (Koo et al. 2022). Research track only. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:108 | Styles: `auto` (default), `smooth` (preserve songs, short blends), `club` (long beatmatched/stem blends), `creative` (echo, pitch, acapella). | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:111 | MixScript is compiled into a graph: per-track/per-stem **gain automation**, **3-band DJ EQ** (Linkwitz-Riley isolator), | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:112 | **HPF/LPF** with resonance, **delay/echo** with beat-synced time, **time-stretch** + optional pitch, **limiter** on the master. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:113 | - Time-stretch: **Signalsmith Stretch** (MIT) default; Rubber Band (GPL) optional via subprocess, never linked. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:114 | - Automation curves are sample-accurate and smoothed (no zipper noise); stems are re-summed with phase-aligned latency compensation. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:115 | - Render only the transition window + copy untouched regions → fast previews (< 2 s per candidate target on M4). | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:116 | - Output: WAV/FLAC, plus 30 s preview MP3/OGG of each candidate. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:119 | Re-analyse the rendered seam: beat-phase drift (ms), tempo continuity, short-term loudness curve (max dip/bump in LU), | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:120 | low-band (< 150 Hz) energy overlap, vocal overlap seconds, clipping/true-peak, spectral flux spikes (clicks). | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:121 | Thresholds fail a candidate → next candidate → finally `trim_crossfade` (always passes). The results go into `report.json` and `report.html` | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:122 | (waveforms, cue markers, curves, score breakdown, rejected candidates and why). | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:125 | Versioned JSON Schema (`mixscript/v1`): track refs (content hash, not path), in/out points, tempo map, per-stem | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:126 | automation lanes (time in **beats** of the reference track, not seconds), effects with params, provenance | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:127 | (analysis backend versions, scorer version, seed). It can be shared without the audio, which makes it copyright-safe and diffable. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:128 | The UI edits MixScripts, models output MixScripts, and tests snapshot MixScripts. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:131 | Pairwise transition-quality matrix (cheap features first, full plan only for top-k) → ordering as an orienteering/TSP | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:132 | problem with an **energy-arc target** (warm-up → peak → cool-down), key-path smoothness, artist/genre variety, | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:133 | and user pins ("start with X", "keep album order"). Then plan each transition and render the whole set with a tracklist + cue sheet (CUE file). | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:137 | - **Python library** `mixconsole` (typed, documented): `analyze()`, `plan()`, `render()`, `verify()`, `mix()`. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:138 | - **CLI** (Typer): | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:139 |   `mixconsole analyze a.mp3` · `mixconsole mix a.mp3 b.mp3 -o out.wav --style auto --candidates 3` · | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:140 |   `mixconsole render plan.mixscript.json` · `mixconsole set ./folder --arc peak -o set.flac` · `mixconsole doctor` | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:141 | - **Console UI** (local web app): FastAPI backend + Vite/React/TypeScript + wavesurfer.js. Drop files → waveform deck A/B | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:142 |   with beat/phrase/section/vocal lanes → candidate cards (play, A/B, score breakdown) → drag cue points, edit curves → | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:143 |   re-render in place → export. Blind A/B voting page feeds the preference dataset (stored locally, export opt-in). | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:144 | - **Later:** desktop shell (Tauri), real-time playback engine for a "player mode", plugin API for new families/backends. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:148 | 1. **Unit + property tests on synthetic audio:** click tracks / generated loops at known BPM, key, phrase length, and | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:149 |    inserted vocals (TTS/sine bursts) → exact expected cues and zero-drift renders. Run in CI, no models needed. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:150 | 2. **Analysis accuracy:** beat/downbeat F-measure on a small public set (GTZAN-rhythm, Ballroom, Harmonix sample), | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:151 |    key accuracy (GiantSteps Key). Run per backend → pick defaults by measurement. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:152 | 3. **Transition corpus:** 60+ pairs of **Creative Commons** tracks (FMA/Jamendo/ccMixter CC-BY/CC0) across EDM, hip-hop, | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:153 |    pop, rock, R&B, Bollywood/Indian pop, acoustic, classical; listed in `bench/pairs.yaml` with licenses; never commit audio, fetch script only. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:154 | 4. **Baselines:** plain 6 s crossfade, trim+crossfade, automix-engine (run as an external process), Mixxx Auto DJ; | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:155 |    Apple AutoMix/djay by manual recording only for private listening (never redistributed). | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:156 | 5. **Blind listening:** MUSHRA-lite / pairwise A/B in the console; ≥ 10 listeners, randomised, report win-rate with CI. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:157 |    Results are published in `bench/results/` with the date and commit. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:158 | 6. **Performance budget (M4 16 GB):** analysis of a 4-min track ≤ 20 s without stems, ≤ 60 s with stems (MPS); | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:159 |    plan+render of 3 candidates ≤ 10 s with cache; peak RAM ≤ 4 GB. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:163 | - Repo: `roop37/mixconsole` (public when M1 is demo-able). Default branch `main`, PRs only, squash merge. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:164 | - License: **Apache-2.0** recommended (patent grant; compatible with MIT/BSD deps; GPL tools only via subprocess). | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:165 |   Model weights keep their own licenses, listed in `THIRD_PARTY.md`. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:166 | - Docs: README with audio demos (CC music) + 30-second quickstart, CONTRIBUTING (issue-first for features, | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:167 |   conventional commits, `scripts/check.sh` must pass), CODE_OF_CONDUCT, SECURITY, issue/PR templates (PR body style that | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:168 |   worked on KeepTrack: what, decisions, files table, tests, screenshots/audio, open questions), CHANGELOG via release-please, | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:169 |   `AGENTS.md` for AI contributors. **No AI attribution lines in commits or PRs.** | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:170 | - Tooling: Python 3.12, `uv`, ruff (lint+format), pyright (strict on core), pytest (+ hypothesis), pre-commit; | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:171 |   GitHub Actions: lint/type/test (fast, model-free) on Linux/macOS + nightly slow job with models; frontend: pnpm, Vite, Biome, Vitest, Playwright smoke. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:172 | - Packaging: `pip install mixconsole` (core, DSP only) and extras `[neural]`, `[stems]`, `[ui]`, `[all]`; models are downloaded on first use | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:173 |   into the cache with checksums; `mixconsole doctor` reports what's installed. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:174 | - Labels: `good first issue`, `transition-family`, `backend`, `bench`. Discussions on for "show your mix". | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:175 | - Copyright: never commit or ship commercial audio; demos are CC-only with attribution. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:179 | The engine must serve three clients without rewrites: the CLI, the local web console, and later a desktop shell or player. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:180 | So the boundaries are fixed now: | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:192 | 1. **Service facade** (`mixconsole.service`): the single entry point used by CLI and server. Every long operation takes | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:193 |    a `Progress` callback (stage, fraction, message) and a `CancelToken`; nothing in the engine prints or reads the CLI. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:194 | 2. **Jobs**: analysis/render run as jobs (id, state, progress, result ref, error) in a process pool. The CLI runs them | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:195 |    inline; the server queues them and streams progress over SSE. Concurrency is bounded by RAM (stems ≈ 2–3 GB each). | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:196 | 3. **Projects**: a project = tracks (hash → original path, user metadata) + analyses + MixScript versions (append-only | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:197 |    history, enabling undo and diff in the UI) + renders. Stored in `project.sqlite` + artifact folder; portable. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:198 | 4. **Library index**: SQLite (`index.sqlite`) of every analysed track: hash, path(s), duration, bpm, key, LUFS, energy | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:199 |    summary, backend versions, and later embeddings. This makes multi-track planning over thousands of tracks a query, not | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:200 |    a re-scan. Batch analysis = parallel workers + resumable queue. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:201 | 5. **Frontend artifacts are precomputed by the engine**: multi-resolution waveform peaks (JSON/binary, wavesurfer-compatible), | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:202 |    beat/bar/phrase/section/vocal lanes, preview encodes (Opus/MP3) served with HTTP range requests. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:203 | 6. **One contract, generated types**: pydantic models → JSON Schema (`schemas/`) → OpenAPI → generated TypeScript | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:204 |    types (`packages/schema-ts`). CI fails if generated files drift. The UI never hand-writes API types. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:205 | 7. **Editability in the contract**: MixScript gets stable ids for transitions, lanes and points, per-transition | wrong | see actionable findings above |
| PLAN.md:206 |    explanation + candidate list, and **user locks** (pinned cue/length/family/lanes the planner must respect on re-plan). | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:207 |    This is MixScript v1.1 (additive, migration provided) and is delivered before M2 renders depend on it. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:208 | 8. **Extensibility**: backends and transition families register via Python entry points (`mixconsole.backends`, | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:209 |    `mixconsole.families`), so third parties can ship plugins without forking. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:210 | 9. **Config + models**: `pydantic-settings` config (`~/.config/mixconsole/config.toml`, env `MIXCONSOLE_*`); a model | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:211 |    manager downloads weights on demand with sha256 pins, license notice, offline mode and `mixconsole models list/fetch`. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:212 | 10. **Long audio**: streaming/chunked decode so 1-hour DJ mixes and sets don't need to fit in RAM twice; arrays in `.npz` | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:213 |     or memory-mapped `.npy`. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:214 | 11. **Determinism scope**: identical bytes are guaranteed only on the same platform + dependency lock; cross-platform | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:215 |     golden tests compare with tolerances (sample error < −90 dBFS, cue positions exact). | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:216 | 12. **Repo layout as it grows**: Python engine stays at root (`src/mixconsole`); the web console lives in `apps/console` | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:217 |     (pnpm workspace); generated TS types in `packages/schema-ts`; docs site in `docs/` (MkDocs Material + mkdocstrings). | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:221 | / Kind / What / Where / Gate / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:223 | / Perf / time + peak RSS per stage (decode, each analysis backend, plan, render, verify) for 30 s / 4 min / 10 min / 60 min inputs / `bench/perf` via `mixconsole bench perf`, JSON results with machine fingerprint + git sha / budget table in §5; regressions > 20 % flagged (nightly, non-blocking on shared CI runners) / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:224 | / Accuracy (synthetic) / tempo, beats, downbeats, phrases, key, loudness, edges against exact ground truth / `bench/accuracy` + pytest / blocking in CI / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:225 | / Accuracy (public annotations) / beat/downbeat (Ballroom, GTZAN-rhythm annotations), key + tempo (GiantSteps) with user-fetched audio / `bench/datasets/*.yaml` manifests + fetch scripts, audio never committed / reported per backend; chooses defaults / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:226 | / Transition quality / seam metrics on the CC corpus vs baselines / `bench/transitions` (M4) / reported / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:227 | / Listening / blind A/B / MUSHRA-lite / console (M5) / published results / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:228 | / Docs / README/docs code blocks executed as tests, link check, markdownlint, schema docs generated / CI `docs` job / blocking / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:229 | / Supply chain / license allowlist check on the lock (deny GPL/AGPL/NC in core), `pip-audit`, Dependabot, pinned actions / CI / blocking / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:231 | Results live in `bench/results/<date>-<sha>-<machine>.json` plus a generated `bench/results/LATEST.md`. | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:235 | / Risk / Mitigation / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:237 | / Stem separation slow / heavy / only separate ~60 s windows; cache; stem-free families as fallback / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:238 | / Model licenses (madmom models, RoFormer weights NC) / backend interface + license registry; defaults MIT/Apache only / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:239 | / allin1/NATTEN hard to install on macOS / optional extra; in-house section fallback / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:240 | / Genre generalisation (CUE-DETR is EDM-trained) / per-genre bench + heuristic cues; family-genre priors / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:241 | / "Better than Apple" is unprovable without tests / honesty rule; publish blind tests / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| PLAN.md:242 | / Scope creep / ROADMAP milestones, each with acceptance tests and a demo / | not yet true | design target; ROADMAP milestone allocation, src module inspection |
| ROADMAP.md:3 | One milestone at a time. A milestone is **done** only when `scripts/check.sh` passes and its acceptance list is met with | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| ROADMAP.md:4 | recorded evidence (logs, rendered audio paths, report.html) in `planning/Mxx-*.md`. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| ROADMAP.md:6 | / # / Milestone / Outcome / Acceptance (summary) / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| ROADMAP.md:8 | / M0 / Foundation / Repo skeleton, tooling, CI, docs, MixScript v1 schema, synthetic-audio test kit / `uv sync`, `scripts/check.sh` green; schema validates examples; synthetic generator makes click tracks with known BPM/phrases / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| ROADMAP.md:9 | / M1 / Analysis core / `mixconsole analyze` → cached TrackAnalysis (beats, downbeats, tempo map, phrases, key, loudness, energy, silence, sections fallback) / Synthetic: BPM within 0.1, downbeats exact, phrases exact; cache hit < 0.2 s; Beat This! backend behind `[neural]` / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| ROADMAP.md:10 | / M1H / Hardening + bench harness / MixScript v1.1 (ids, locks, per-transition explanation/candidates), service facade with progress/cancel, config, entry-point registry, perf + accuracy bench harness, docs validation, supply-chain CI / `mixconsole bench perf/accuracy` writes results + LATEST.md; README code blocks run in tests; license allowlist + pip-audit + link check green; v1→v1.1 migration tested / | not yet true | milestone acceptance target; not a completed-status assertion |
| ROADMAP.md:11 | / M2 / Two-song mix v0.1 / Planner (families 1–4, 6, 7), heuristic scorer, renderer (gain/EQ/filters/echo/stretch/limiter), verify + fallback, `mixconsole mix a b` / Synthetic pairs: drift < 5 ms, loudness dip < 1.5 LU, no clipping; 3 candidates + report.html; deterministic renders (hash-equal) / | not yet true | milestone acceptance target; not a completed-status assertion |
| ROADMAP.md:12 | / M3 / Stems + vocals / Demucs windows, vocal activity + lyric gaps, `stem_handoff`, `vocal_over_instrumental`, bass/vocal clash rules / No lead-vocal overlap on test pairs; stems cached per window; works without stems installed / | not yet true | milestone acceptance target; not a completed-status assertion |
| ROADMAP.md:13 | / M4 / Bench / CC corpus fetch script, baselines (crossfade, automix-engine external), metrics dashboard, analysis-accuracy eval / `bench/run.sh` produces results table + listening pages / | not yet true | milestone acceptance target; not a completed-status assertion |
| ROADMAP.md:14 | / M4.5 / Service + API / Projects (SQLite), library index, job queue + SSE progress, waveform peaks, preview encodes with range requests, FastAPI + OpenAPI → generated TS types / API contract tests; 100-track batch analysis resumable; TS types drift check in CI / | not yet true | milestone acceptance target; not a completed-status assertion |
| ROADMAP.md:15 | / M5 / Console UI / Local web app: decks, lanes, candidate audition, cue drag, curve edit, re-render, export, blind A/B voting / Playwright smoke: load 2 files → audition → edit cue → export / | not yet true | milestone acceptance target; not a completed-status assertion |
| ROADMAP.md:16 | / M6 / Multi-track sets / Transition matrix, energy-arc ordering, set render + CUE sheet, `mixconsole set` / 10-track folder → ordered set with report; user pins respected / | not yet true | milestone acceptance target; not a completed-status assertion |
| ROADMAP.md:17 | / M7 / Learned ranker / Preference data from A/B tool, LightGBM ranker, held-out pair evaluation / Ranker beats heuristic on held-out pairs (pairwise accuracy, CI reported) / | not yet true | milestone acceptance target; not a completed-status assertion |
| ROADMAP.md:18 | / M8 / Release 0.1 / PyPI package, docs site, demo audio, public repo, launch post / Fresh-machine install < 2 min; README demos; tagged release / | not yet true | milestone acceptance target; not a completed-status assertion |
| ROADMAP.md:19 | / R  / Research track / DJtransGAN-style curve model, mix-to-track alignment dataset, real-time player, Tauri desktop / Separate proposals / | not yet true | milestone acceptance target; not a completed-status assertion |
| THIRD_PARTY.md:3 | No model weights are installed by the core. M1 adds the optional `neural` extra | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:4 | (also included by `all`). These tables record all Python packages in `uv.lock`, | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:5 | including transitive and platform-specific dependencies. Versions are pinned in the lockfile. License identifiers come from | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:6 | the installed distributions’ metadata and license files; each link identifies the | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:7 | upstream distribution. Preserve the license notices shipped in dependency wheels. | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:9 | / Dependency / Role / License / URL / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:11 | / annotated-doc / Transitive / MIT / [PyPI](https://pypi.org/project/annotated-doc/0.0.6/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:12 | / annotated-types / Transitive / MIT / [PyPI](https://pypi.org/project/annotated-types/0.8.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:13 | / certifi / Transitive / MPL-2.0 / [PyPI](https://pypi.org/project/certifi/2026.10.23/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:14 | / cffi / Transitive / MIT-0 / [PyPI](https://pypi.org/project/cffi/2.1.1/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:15 | / cfgv / Transitive / MIT / [PyPI](https://pypi.org/project/cfgv/3.5.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:16 | / charset-normalizer / Transitive / MIT / [PyPI](https://pypi.org/project/charset-normalizer/3.5.2/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:17 | / cloudpickle / Transitive / BSD-3-Clause / [PyPI](https://pypi.org/project/cloudpickle/3.1.2/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:18 | / colorama / Transitive / Windows / MIT / [PyPI](https://pypi.org/project/colorama/0.4.6/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:19 | / decorator / Transitive / BSD-2-Clause / [PyPI](https://pypi.org/project/decorator/5.3.1/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:20 | / distlib / Transitive / PSF-2.0 / [PyPI](https://pypi.org/project/distlib/0.4.4/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:21 | / filelock / Transitive / MIT / [PyPI](https://pypi.org/project/filelock/4.2.11/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:22 | / hypothesis / Development / MPL-2.0 / [PyPI](https://pypi.org/project/hypothesis/6.170.15/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:23 | / identify / Transitive / MIT / [PyPI](https://pypi.org/project/identify/2.6.20/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:24 | / idna / Transitive / BSD-3-Clause / [PyPI](https://pypi.org/project/idna/3.20/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:25 | / iniconfig / Transitive / MIT / [PyPI](https://pypi.org/project/iniconfig/2.3.1/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:26 | / joblib / Transitive / BSD-3-Clause / [PyPI](https://pypi.org/project/joblib/1.6.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:27 | / lazy-loader / Transitive / BSD-3-Clause / [PyPI](https://pypi.org/project/lazy-loader/0.6/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:28 | / librosa / Core / ISC / [PyPI](https://pypi.org/project/librosa/1.0.1/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:29 | / llvmlite / Transitive / BSD-2-Clause AND Apache-2.0 WITH LLVM-exception / [PyPI](https://pypi.org/project/llvmlite/0.50.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:30 | / markdown-it-py / Transitive / MIT / [PyPI](https://pypi.org/project/markdown-it-py/4.3.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:31 | / mdurl / Transitive / MIT / [PyPI](https://pypi.org/project/mdurl/0.1.2/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:32 | / msgpack / Transitive / Apache-2.0 / [PyPI](https://pypi.org/project/msgpack/1.2.4/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:33 | / narwhals / Transitive / MIT / [PyPI](https://pypi.org/project/narwhals/2.29.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:34 | / nodeenv / Transitive / BSD-3-Clause / [PyPI](https://pypi.org/project/nodeenv/1.12.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:35 | / numba / Transitive / BSD-2-Clause / [PyPI](https://pypi.org/project/numba/0.68.1/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:36 | / numpy / Core / BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 / [PyPI](https://pypi.org/project/numpy/2.5.5/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:37 | / packaging / Transitive / Apache-2.0 OR BSD-2-Clause / [PyPI](https://pypi.org/project/packaging/26.3/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:38 | / platformdirs / Transitive / MIT / [PyPI](https://pypi.org/project/platformdirs/4.14.7/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:39 | / pluggy / Transitive / MIT / [PyPI](https://pypi.org/project/pluggy/1.7.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:40 | / pooch / Transitive / BSD-3-Clause / [PyPI](https://pypi.org/project/pooch/1.9.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:41 | / pre-commit / Development / MIT / [PyPI](https://pypi.org/project/pre-commit/4.7.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:42 | / pycparser / Transitive / BSD-3-Clause / [PyPI](https://pypi.org/project/pycparser/3.12/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:43 | / pydantic / Core / MIT / [PyPI](https://pypi.org/project/pydantic/2.14.3/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:44 | / pydantic-core / Transitive / MIT / [PyPI](https://pypi.org/project/pydantic-core/2.50.4/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:45 | / pygments / Transitive / BSD-2-Clause / [PyPI](https://pypi.org/project/pygments/2.21.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:46 | / pyloudnorm / Core / MIT / [PyPI](https://pypi.org/project/pyloudnorm/0.2.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:47 | / pyright / Development / MIT / [PyPI](https://pypi.org/project/pyright/1.1.414/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:48 | / pytest / Development / MIT / [PyPI](https://pypi.org/project/pytest/9.2.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:49 | / python-discovery / Transitive / MIT / [PyPI](https://pypi.org/project/python-discovery/1.9.5/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:50 | / pyyaml / Core / MIT / [PyPI](https://pypi.org/project/pyyaml/6.0.3/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:51 | / requests / Transitive / Apache-2.0 / [PyPI](https://pypi.org/project/requests/2.34.2/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:52 | / rich / Core / MIT / [PyPI](https://pypi.org/project/rich/15.0.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:53 | / ruff / Development / MIT / [PyPI](https://pypi.org/project/ruff/0.17.5/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:54 | / scikit-learn / Transitive / BSD-3-Clause / [PyPI](https://pypi.org/project/scikit-learn/1.9.1/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:55 | / scipy / Core / BSD-3-Clause (bundled notices also apply) / [PyPI](https://pypi.org/project/scipy/1.18.1/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:56 | / shellingham / Transitive / ISC / [PyPI](https://pypi.org/project/shellingham/1.5.4/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:57 | / sortedcontainers / Transitive / Apache-2.0 / [PyPI](https://pypi.org/project/sortedcontainers/2.4.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:58 | / soundfile / Core / BSD-3-Clause (libsndfile: LGPL-2.1-or-later) / [PyPI](https://pypi.org/project/soundfile/0.14.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:59 | / soxr / Transitive / LGPL-2.1-or-later / [PyPI](https://pypi.org/project/soxr/1.1.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:60 | / threadpoolctl / Transitive / BSD-3-Clause / [PyPI](https://pypi.org/project/threadpoolctl/3.8.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:61 | / typer / Core / MIT / [PyPI](https://pypi.org/project/typer/0.29.1/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:62 | / typing-extensions / Transitive / PSF-2.0 / [PyPI](https://pypi.org/project/typing-extensions/4.16.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:63 | / typing-inspection / Transitive / MIT / [PyPI](https://pypi.org/project/typing-inspection/0.4.5/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:64 | / urllib3 / Transitive / MIT / [PyPI](https://pypi.org/project/urllib3/2.8.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:65 | / virtualenv / Transitive / MIT / [PyPI](https://pypi.org/project/virtualenv/21.15.8/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:69 | / Component / Role / License / URL / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:71 | / hatchling / PEP 517 build backend / MIT / [Hatch](https://github.com/pypa/hatch) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:72 | / pathspec / Hatchling build dependency / MPL-2.0 / [pathspec](https://github.com/cpburnz/python-pathspec) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:73 | / tomlkit / Hatchling build dependency / MIT / [tomlkit](https://github.com/python-poetry/tomlkit) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:74 | / trove-classifiers / Hatchling build dependency / Apache-2.0 / [trove-classifiers](https://github.com/pypa/trove-classifiers) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:75 | / libsndfile / Native SoundFile decoder, supplied by wheels or system / LGPL-2.1-or-later / [libsndfile](https://libsndfile.github.io/libsndfile/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:76 | / libsoxr / Native library behind librosa’s soxr dependency / LGPL-2.1-or-later / [SoX resampler](https://sourceforge.net/projects/soxr/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:77 | / libFLAC / Codec optionally bundled with libsndfile / BSD-3-Clause (library) / [FLAC](https://xiph.org/flac/license.html) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:78 | / libogg / libvorbis / Codecs optionally bundled with libsndfile / BSD-3-Clause / [Xiph licensing](https://www.xiph.org/licenses/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:79 | / mpg123 / libmpg123 / Decoder optionally bundled with libsndfile / LGPL-2.1-or-later / [mpg123](https://www.mpg123.de/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:80 | / OpenBLAS / May be bundled in NumPy/SciPy wheels / BSD-3-Clause / [OpenBLAS](https://github.com/OpenMathLib/OpenBLAS) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:81 | / LAPACK / May be bundled in numerical wheels / BSD-3-Clause / [LAPACK](https://github.com/Reference-LAPACK/lapack) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:82 | / LLVM / Bundled by llvmlite / Apache-2.0 WITH LLVM-exception / [LLVM license](https://llvm.org/docs/DeveloperPolicy.html#license) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:83 | / GCC runtime libraries / May be bundled in numerical wheels / GPL-3.0-or-later WITH GCC-exception-3.1 / [GCC runtime exception](https://www.gnu.org/licenses/gcc-exception-3.1.html) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:84 | / ffmpeg / Optional system executable; subprocess only, not shipped or linked / LGPL-2.1-or-later or GPL-2.0-or-later depending on build / [FFmpeg legal](https://ffmpeg.org/legal.html) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:85 | / uv / Environment and packaging tool / MIT OR Apache-2.0 / [uv](https://github.com/astral-sh/uv) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:86 | / actions/checkout / CI checkout action / MIT / [checkout](https://github.com/actions/checkout) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:87 | / astral-sh/setup-uv / CI uv setup action / MIT OR Apache-2.0 / [setup-uv](https://github.com/astral-sh/setup-uv) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:88 | / Node.js / Pyright runtime when not already installed / MIT plus bundled notices / [Node.js](https://github.com/nodejs/node/blob/main/LICENSE) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:89 | / Pyright / Type checker bundled by the Python wrapper / MIT / [Pyright](https://github.com/microsoft/pyright) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:91 | Hatchling also uses packaging and pluggy, listed above. Native components depend on | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:92 | the installed wheel/platform; their bundled notices remain authoritative. The | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:93 | requested SoundFile/librosa dependencies bring LGPL native libraries. No source | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:94 | code from these or any GPL/LGPL/AGPL project is copied into MixConsole. Optional | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:95 | GPL tools are invoked only as external processes. No non-commercial weights are | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:96 | defaults, and no audio or model weights are distributed. | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:100 | Core dependencies are unchanged. These additions are resolved by `uv.lock` but | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:101 | are installed only for `neural`/`all`. Licenses were checked against PyPI metadata | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:102 | and wheel license files; CUDA binary distributions retain their vendor terms. | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:103 | CUDA/NVIDIA/Triton packages are platform-specific torch dependencies and are not | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:104 | installed on macOS or required by core analysis. | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:106 | / Dependency / Role / License / URL / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:108 | / beat-this / Optional neural backend / MIT / [PyPI](https://pypi.org/project/beat-this/1.1.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:109 | / cuda-bindings / Optional neural transitive / Apache-2.0 / [PyPI](https://pypi.org/project/cuda-bindings/13.5.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:110 | / cuda-pathfinder / Optional neural transitive / Apache-2.0 / [PyPI](https://pypi.org/project/cuda-pathfinder/1.9.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:111 | / cuda-toolkit / Optional neural transitive / NVIDIA CUDA EULA (metapackage; component licenses apply) / [PyPI](https://pypi.org/project/cuda-toolkit/13.2.2/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:112 | / einops / Optional neural transitive / MIT / [PyPI](https://pypi.org/project/einops/0.8.2/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:113 | / fsspec / Optional neural transitive / BSD-3-Clause / [PyPI](https://pypi.org/project/fsspec/2026.9.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:114 | / jinja2 / Optional neural transitive / BSD-3-Clause / [PyPI](https://pypi.org/project/jinja2/3.1.6/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:115 | / markupsafe / Optional neural transitive / BSD-3-Clause / [PyPI](https://pypi.org/project/markupsafe/3.0.4/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:116 | / mpmath / Optional neural transitive / BSD-3-Clause / [PyPI](https://pypi.org/project/mpmath/1.3.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:117 | / networkx / Optional neural transitive / BSD-3-Clause / [PyPI](https://pypi.org/project/networkx/3.7/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:118 | / nvidia-cublas / Optional neural transitive / NVIDIA CUDA EULA / [PyPI](https://pypi.org/project/nvidia-cublas/13.4.1.3/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:119 | / nvidia-cuda-cccl / Optional neural transitive / LicenseRef-NVIDIA-Proprietary / [PyPI](https://pypi.org/project/nvidia-cuda-cccl/13.3.5.0.6/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:120 | / nvidia-cuda-cupti / Optional neural transitive / NVIDIA CUDA EULA / [PyPI](https://pypi.org/project/nvidia-cuda-cupti/13.2.86/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:121 | / nvidia-cuda-nvrtc / Optional neural transitive / NVIDIA CUDA EULA / [PyPI](https://pypi.org/project/nvidia-cuda-nvrtc/13.2.86/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:122 | / nvidia-cuda-runtime / Optional neural transitive / NVIDIA CUDA EULA / [PyPI](https://pypi.org/project/nvidia-cuda-runtime/13.2.86/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:123 | / nvidia-cudnn-cu13 / Optional neural transitive / NVIDIA Software Development Kits license / [PyPI](https://pypi.org/project/nvidia-cudnn-cu13/9.26.0.51/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:124 | / nvidia-cufft / Optional neural transitive / NVIDIA CUDA EULA / [PyPI](https://pypi.org/project/nvidia-cufft/12.2.0.57/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:125 | / nvidia-cufile / Optional neural transitive / NVIDIA CUDA EULA / [PyPI](https://pypi.org/project/nvidia-cufile/1.17.1.22/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:126 | / nvidia-cusolver / Optional neural transitive / NVIDIA CUDA EULA / [PyPI](https://pypi.org/project/nvidia-cusolver/12.2.0.11/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:127 | / nvidia-cusparse / Optional neural transitive / NVIDIA CUDA EULA / [PyPI](https://pypi.org/project/nvidia-cusparse/12.7.10.12/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:128 | / nvidia-cusparselt-cu13 / Optional neural transitive / NVIDIA Proprietary Software / [PyPI](https://pypi.org/project/nvidia-cusparselt-cu13/0.8.1/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:129 | / nvidia-nccl-cu13 / Optional neural transitive / BSD-3-Clause / [PyPI](https://pypi.org/project/nvidia-nccl-cu13/2.30.7/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:130 | / nvidia-nvjitlink / Optional neural transitive / LicenseRef-NVIDIA-Proprietary / [PyPI](https://pypi.org/project/nvidia-nvjitlink/13.5.37/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:131 | / nvidia-nvshmem-cu13 / Optional neural transitive / NVIDIA CUDA EULA / [PyPI](https://pypi.org/project/nvidia-nvshmem-cu13/3.7.2/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:132 | / nvidia-nvtx / Optional neural transitive / Apache-2.0 / [PyPI](https://pypi.org/project/nvidia-nvtx/13.2.86/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:133 | / rotary-embedding-torch / Optional neural transitive / MIT / [PyPI](https://pypi.org/project/rotary-embedding-torch/0.9.2/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:134 | / setuptools / Optional neural transitive / MIT / [PyPI](https://pypi.org/project/setuptools/84.2.1/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:135 | / sympy / Optional neural transitive / BSD-3-Clause AND MIT (bundled parser) / [PyPI](https://pypi.org/project/sympy/1.14.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:136 | / torch / Optional neural runtime / Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND ISC AND MIT AND Zlib / [PyPI](https://pypi.org/project/torch/2.15.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:137 | / torchaudio / Optional neural transitive / BSD-2-Clause / [PyPI](https://pypi.org/project/torchaudio/2.11.1/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:138 | / triton / Optional neural transitive / MIT / [PyPI](https://pypi.org/project/triton/3.9.0/) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:140 | NVIDIA CUDA binary EULA: [official terms](https://docs.nvidia.com/cuda/eula/index.html). | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:141 | cuDNN SDK terms: [official license](https://docs.nvidia.com/deeplearning/cudnn/backend/latest/reference/eula.html). | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:142 | `cuda-toolkit` is a dependency-only metapackage with no wheel license file; the | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:143 | installed components' EULAs/notices apply. Torch's license expression above includes | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:144 | its bundled components; upstream torch itself uses BSD-3-Clause. | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:146 | / Optional model / reserved integration / Status / License / URL / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:148 | / Beat This! published checkpoints / User-supplied local checkpoint only; SHA-256 recorded in analysis provenance; no automatic download or bundled weights / MIT (code and published weights) / [Upstream model/license documentation](https://github.com/CPJKU/beat_this#license) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:149 | / All-In-One (`allin1`) / Reserved lazy section stub only; not installed, executed or distributed; NATTEN compatibility and upstream madmom dependency need review before enabling / MIT (upstream code) / [Upstream](https://github.com/mir-aidj/all-in-one) / | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:151 | No NATTEN, madmom, or non-commercial model weights are added to the environment. | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:152 | The All-In-One stub always resolves to the in-house novelty backend in M1. Its | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:153 | upstream NATTEN build depends on torch/CUDA/platform compatibility, with a macOS | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:154 | installation caveat; see [installation](https://github.com/mir-aidj/all-in-one#installation). | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:156 | The key backend uses published numeric Krumhansl–Kessler and Temperley profiles, | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:157 | plus an original EDMA-style triadic profile. Profiles are algorithm parameters, | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:158 | not copied implementation code or learned weights. CQT, key scoring, phase/phrase | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| THIRD_PARTY.md:159 | selection, section novelty and edge rules contain no copied copyleft source. | verified | uv.lock + installed metadata; generated license inventory will replace manual table |
| CHANGELOG.md:7 | - M0 package foundation, uv tooling, CI, contributor documents and Apache-2.0 license. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| CHANGELOG.md:8 | - MixScript v1 models, JSON Schema, example plans and CLI validation. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| CHANGELOG.md:9 | - Seeded synthetic audio with beat, downbeat, phrase, key and vocal annotations. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| CHANGELOG.md:10 | - Canonical stereo audio decoding, WAV/FLAC writing and PCM/file hashing. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| CHANGELOG.md:11 | - Environment diagnostics and version command. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| CHANGELOG.md:13 | - M1 TrackAnalysis v1 with JSON Schema and compact NPZ feature curves. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| CHANGELOG.md:14 | - Typed analysis backends: core beat/downbeat tracking, tempo continuity, key profile | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| CHANGELOG.md:15 |   ensemble, LUFS/true-peak estimates, bar energy, phrases, sections and edge cues. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| CHANGELOG.md:16 | - Optional lazy Beat This! adapter with core fallback and checkpoint provenance; | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| CHANGELOG.md:17 |   reserved All-In-One section adapter stub with documented NATTEN caveat. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| CHANGELOG.md:18 | - Public `mixconsole.analyze`, rich multi-file CLI, JSON export and cache management. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| CHANGELOG.md:19 | - Atomic PCM/version-addressed cache, integrity validation, cache bypass and overrides. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| CHANGELOG.md:20 | - Synthetic analysis acceptance tests and reproducible four-minute benchmark. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| CHANGELOG.md:21 | - Optional phrase-grid offset in the existing seeded synthetic generator. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| CHANGELOG.md:23 | Transition planning, rendering and UI remain future milestones. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:3 | Status: complete. Local validation: macOS arm64, Python 3.12.16, 2026-11-18. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:7 | - [x] Read `PLAN.md`, `ROADMAP.md`, and `AGENTS.md` fully before changes; M0 only. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:8 | - [x] `pyproject.toml`: uv project, Python >=3.12, Apache-2.0, src package, typed | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:9 |   marker, Typer entry point, requested core/dev dependencies, and four empty extras. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:10 |   `uv.lock` records the resolved environment; `.python-version` selects 3.12 locally. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:11 | - [x] Package directories follow `AGENTS.md`; future analysis/planning/scoring/ | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:12 |   rendering/verification/reporting modules contain only docstrings. `bench/` and | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:13 |   `ui/` document their future milestones. The scorer weight file is empty. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:14 | - [x] Executable `scripts/check.sh`: ruff check, format check, strict core pyright, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:15 |   and `pytest -m "not slow"`, stopping on a failing command. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:16 | - [x] `src/mixconsole/mixscript/`: v1 models, full validation, stable schema export, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:17 |   provenance, explanation/rejected candidates, track/stem automation, tempo map, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:18 |   cue positions, key strategy and effects. `scripts/gen_schema.py` regenerates | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:19 |   `schemas/mixscript-v1.json`; tests compare the committed schema byte for byte. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:20 | - [x] Two validated illustrative plans in `examples/`: trim crossfade and stem | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:21 |   handoff. Invented hashes do not refer to recordings. Examples do not claim to | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:22 |   have been analyzed or rendered. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:23 | - [x] `src/mixconsole/testing/synth.py`, re-exported by `tests/synth.py`: stereo | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:24 |   float32 44.1 kHz clicks/kicks, downbeat accents, seeded phrase crashes, root bass, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:25 |   major/minor pads, voiced formant-like bursts, silence, and a tempo ramp. Returned | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:26 |   annotations include sample-aligned beats/downbeats/phrases/key/vocal intervals. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:27 | - [x] `src/mixconsole/io/`: SoundFile decode, scipy polyphase resampling, mono to | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:28 |   stereo, optional ffmpeg decode/downmix, canonical PCM SHA-256 and file SHA-256, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:29 |   float WAV and PCM24 FLAC writing, invalid audio rejection. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:30 | - [x] CLI version, doctor and validate commands. Doctor shows Python, ffmpeg, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:31 |   placeholder extras, optional package versions, torch, MPS and CUDA availability. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:32 | - [x] README, contributing guide, Code of Conduct, security policy, full Apache-2.0 | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:33 |   license, changelog, dependency/license registry, three issue templates and the | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:34 |   required six-section PR template. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:35 | - [x] Ubuntu/macOS CI matrix (Python 3.12/3.13), uv locked install, ffmpeg, check.sh; | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:36 |   local pre-commit hooks; ignore rules for caches, environments, audio, output and | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:37 |   model weights. Audio fixtures are generated in temporary test directories. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:38 | - [x] No added torch/model dependency, audio asset, model weight, or copied | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:39 |   GPL/LGPL/AGPL source code. No commits or remote changes performed. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:40 | - [x] Final `scripts/check.sh` output recorded below. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:44 | Tracks are keyed by portable IDs and carry canonical PCM hashes rather than file | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:45 | paths. Cue beats are source quarter-note positions; automation and tempo-map beats | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:46 | are relative to the transition start on its reference track. `beats_per_bar` is in | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:47 | quarter notes. Gain/send values are linear amplitude, EQ is dB, and filters are Hz. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:48 | Effects describe scalar parameters only; no rendering is implemented in M0. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:50 | Pydantic forbids unknown fields and non-finite numeric values and checks references, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:51 | cue bounds, strictly ordered maps/lanes, unique target/parameter lanes, and valid | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:52 | strategy values. JSON Schema supplies structural validation; full semantic checks | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:53 | use `mixconsole validate`. Pitch/stem feasibility is future planner work. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:55 | Synthetic time signatures count denominator pulses, with BPM in quarter notes. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:56 | Ramp BPM is linear in quarter-note position and integrated analytically, then | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:57 | rounded to actual sample indices. Vocal regions are half-open intervals. Random | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:58 | noise uses a local seeded NumPy generator. Tests do not depend on recorded music. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:60 | WAV preserves float32 samples; FLAC quantizes to PCM24 and rejects out-of-range | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:61 | input instead of silently clipping. PCM hashes are SHA-256 of C-order little-endian | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:62 | float32 stereo samples at 44.1 kHz. Determinism is verified within the installed | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:63 | software environment; codec/resampler changes can alter PCM across environments. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:67 | 1. `cat PLAN.md ROADMAP.md AGENTS.md` — read the full architecture, roadmap and rules. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:68 |    Initial `git status --short` showed only those three user-provided files untracked. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:69 | 2. `UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.cache/python" uv sync --all-extras --dev` | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:70 |    — succeeded; Python 3.12.16, 56 resolved packages including this project, 55 | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:71 |    installed distributions on macOS. The initial attempt without a local Python | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:72 |    install directory hit the sandbox's home-directory write restriction; the local | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:73 |    cache resolved it. These caches are ignored. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:74 | 3. `UV_CACHE_DIR="$PWD/.cache/uv" uv run python scripts/gen_schema.py` — wrote | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:75 |    `schemas/mixscript-v1.json`. Both examples validate and round-trip through models. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:76 | 4. `UV_CACHE_DIR="$PWD/.cache/uv" uv run ruff check --fix .` and | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:77 |    `UV_CACHE_DIR="$PWD/.cache/uv" uv run ruff format .` — normalized imports and | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:78 |    formatting. Initial checks also found typing issues and adjacent-pair iteration | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:79 |    warnings; corrected with typed factories and `itertools.pairwise`. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:80 | 5. `scripts/check.sh` — initial test run found doctor interpreting bracketed extra | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:81 |    names as Rich markup and a helper alias accidentally collected as a test. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:82 |    Both corrected. Subsequent run: **71 passed**, no warnings; pyright had zero errors. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:83 | 6. `UV_CACHE_DIR="$PWD/.cache/uv" uv run mixconsole --version` — `mixconsole 0.0.1`. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:84 | 7. `UV_CACHE_DIR="$PWD/.cache/uv" uv run mixconsole doctor` — Python 3.12.16; | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:85 |    `/opt/homebrew/bin/ffmpeg` present; torch, Beat This!, Demucs and FastAPI absent; | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:86 |    MPS/CUDA unavailable; all extras correctly identified as placeholders. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:87 | 8. `UV_CACHE_DIR="$PWD/.cache/uv" uv run mixconsole validate examples/trim-crossfade.mixscript.json` | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:88 |    and the same command for `examples/stem-handoff.mixscript.json` — both returned | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:89 |    `Valid mixscript/v1: 2 tracks, 1 transitions` with exit status 0. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:90 | 9. `UV_CACHE_DIR="$PWD/.cache/uv" uv build` — built the sdist and wheel in ignored | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:91 |    `dist/`. Inspected archive entries with Python `tarfile`/`zipfile`: no cache, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:92 |    virtualenv or git internals included; wheel contains the testing kit and | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:93 |    `py.typed`. Reviewed installed distribution metadata/license files for | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:94 |    `THIRD_PARTY.md`, including all locked transitive packages and build dependencies. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:96 | Test evidence is in `tests/test_mixscript.py`, `tests/test_synth.py`, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:97 | `tests/test_io.py`, and `tests/test_cli.py`. Coverage includes deterministic WAV/FLAC | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:98 | bytes, cross-container PCM hashes, mono resampling, real ffmpeg AAC fallback and | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:99 | six-channel downmix, bad/missing input, no-torch imports, CLI failures, independent | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:100 | constant/ramped timing calculations, non-4/4 signatures, vocal bounds, key spectrum, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:101 | seeded repeats, and deterministic Hypothesis cases. No tests were skipped locally. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:103 | CI configuration is supplied; hosted Ubuntu/macOS jobs were not executed in this | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:104 | local session. Later milestones' analyze/mix/render/UI behavior remains unimplemented. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:108 | Command: `scripts/check.sh > .cache/m0-final-check.log 2>&1` | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:110 | Exit status: **0**. Verbatim final output: | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:132 | Final setup verification: `UV_CACHE_DIR="$PWD/.cache/uv" uv sync --locked --dev` | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:133 | and `uv sync --locked --all-extras --dev` both succeeded (56 packages resolved, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:134 | 55 installed distributions checked). Final archive inspection confirmed this | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:135 | evidence file, THIRD_PARTY.md, schema and lockfile are in the source distribution, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:136 | with no cache/environment/git internals. The delivered source tree contains no | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M0-foundation.md:137 | audio or model-weight files. All changes remain uncommitted; remotes were untouched. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:3 | Status: complete for the core and optional adapter/stub delivery. Local validation: | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:4 | macOS 27.2.1 arm64, Python 3.12.16, 2026-11-18. Beat This! real-weight inference is | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:5 | conditional and was skipped locally; the adapter contract and fallback were tested. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:6 | M0 was already complete and uncommitted. Its foundation and evidence were preserved; | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:7 | no commits, staging, remote changes, audio assets or model weights were added. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:11 | - [x] Read `PLAN.md` (especially §3.1), `ROADMAP.md`, `AGENTS.md` and | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:12 |   `planning/M0-foundation.md` before changing files. Work remained within M1. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:13 | - [x] `src/mixconsole/analysis/models.py`: finite Pydantic TrackAnalysis v1 contract, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:14 |   file/PCM SHA-256, timing, meter, tempo segments, bars, phrases, sections, key with | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:15 |   three alternatives, loudness, per-bar energy, edges, null vocal activity, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:16 |   backend/dependency versions and fixed seed. Validators enforce musical order, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:17 |   downbeat/phrase membership, phrase bar indices and non-overlapping intervals. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:18 | - [x] `schemas/track-analysis-v1.json`, exported alongside the unchanged MixScript | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:19 |   schema by `scripts/gen_schema.py`; byte-equality test for both schemas. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:20 |   Long short-term loudness and bar-energy arrays use typed sibling NPZ references. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:21 | - [x] Typed BeatBackend, KeyBackend, LoudnessBackend, SectionBackend and CueBackend | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:22 |   Protocols in `analysis/interfaces.py`, with named registries and version provenance. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:23 | - [x] Core onset/DP beats: shared onset envelope, 70–180 BPM interval/autocorrelation | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:24 |   prior, half/double resolution, librosa DP tracking, transient refinement, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:25 |   accent/low-band/harmonic bar phase for 4/4 or 3/4 and median-smoothed tempo maps. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:26 | - [x] Lazy CPU Beat This! adapter in `[neural]`, also included by `[all]`. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:27 |   `beat-this` and `torch` declared; local checkpoint hash recorded; fixed seed; | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:28 |   no DBN/madmom. Missing optional dependencies/checkpoints and runtime failures | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:29 |   warn and fall back. Unknown names fail instead of silently accepting typos. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:30 | - [x] Original CQT key-profile ensemble (Krumhansl–Kessler, Temperley and an original | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:31 |   EDMA-style triadic profile), complete Camelot mapping, probabilistic alternatives. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:32 | - [x] Pyloudnorm integrated loudness; rolling 3 s K-weighted short-term power at | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:33 |   10 Hz; chunked 4x polyphase true-peak estimate. Silence has null scalar LUFS/peak | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:34 |   and a finite -120 LUFS curve floor. Forward windows are zero-padded at EOF. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:35 | - [x] Per-bar RMS/onset/low/mid/high spectral power; 4/8/16-bar phrase grid and | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:36 |   offset chosen using attacks, energy change and chroma/MFCC novelty. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:37 | - [x] Original local self-similarity novelty with peak-picked sections and null | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:38 |   labels. `allin1` is a reserved lazy stub, automatically falling back; NATTEN and | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:39 |   upstream madmom installation caveats documented, with no package installed. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:40 | - [x] -60 dBFS head/tail gate, fade-in/out trends and hard-ending detection. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:41 | - [x] `analysis/cache.py`: PCM/version-addressed directories, environment/argument | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:42 |   overrides, file-hash index, atomic temp/fsync/replace writes, JSON/NPZ pair | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:43 |   integrity checks, corrupt-entry recomputation and explicit no-cache mode. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:44 | - [x] `mixconsole.analyze()` public API, rich multi-file CLI, JSON/NPZ export, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:45 |   `mixconsole cache info/clear`, updated doctor output and README quickstart. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:46 | - [x] Tests use session fixtures and temporary synthesized audio. The existing | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:47 |   generator gained only an additive `phrase_offset_bars` option; existing M0 | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:48 |   defaults/annotations are unchanged. No recorded audio or learned weights used. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:49 | - [x] README, THIRD_PARTY.md, CHANGELOG.md and lockfile updated. Every new optional | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:50 |   direct/transitive dependency and the optional weight family has license + URL. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:51 | - [x] Four-minute benchmark measured; final `scripts/check.sh` passed below. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:55 | `tests/test_analysis.py` uses a one-to-one temporal matcher (±70 ms) for F-measure, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:56 | so duplicate detections cannot inflate scores. Rhythm fixtures use 16 bars, seed | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:57 | 23, pad + bass + kicks/clicks and 8-bar crash markers. Phrase equality is exact | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:58 | sample-aligned float equality, not a tolerance test. A measurement run using the | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:59 | same fixture parameters produced: | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:61 | / Ground-truth BPM / Estimated BPM / Beat F / Downbeat F / 8-bar phrase starts / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:63 | / 90 / 90.000000000 / 1.000 / 1.000 / exact / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:64 | / 100 / 100.000000000 / 1.000 / 1.000 / exact / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:65 | / 124 / 124.000000760 / 1.000 / 1.000 / exact / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:66 | / 128 / 128.000010207 / 1.000 / 1.000 / exact / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:67 | / 140 / 140.000000000 / 1.000 / 1.000 / exact / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:68 | / 174 / 173.999997218 / 1.000 / 1.000 / exact / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:70 | / Other acceptance metric / Measured result / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:72 | / Key tonic + mode, all 24 pad/bass keys / 24/24 (100%); requirement ≥90% / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:73 | / Camelot mapping / All 24 independently ordered wheel entries pass / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:74 | / Ramp 125 → 95 BPM / 8 tempo segments; first 123.125, last 97.108 BPM; beat/downbeat F=1.000 / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:75 | / Ramp 125 → 155 BPM / 8 tempo segments; first 126.873, last 152.895 BPM; beat/downbeat F=1.000 / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:76 | / Shifted phrase grids / Exact starts and lengths for 4 bars/offset 1, 8/offset 2, 16/offset 3 / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:77 | / 3/4 and monotonicity properties / 8 deterministic Hypothesis cases over 75–178 BPM, meter and head silence pass / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:78 | / Pink noise, normalized to −14 LUFS / −14.000000067 LUFS / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:79 | / Head silence, 0.31 s / 0.310000 s / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:80 | / Tail silence, 0.47 s after fade / 0.478163 s (8.2 ms error) / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:81 | / Fade-out / hard-ending distinction / Fade-out true, hard-ending false; abrupt cut separately detected / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:82 | / Short-term LUFS / First 3 s cross-checked against an independent 3 s block meter, <0.02 LU error / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:83 | / Cache hit / Below 0.2 s in acceptance test; 0.056538 s on full four-minute file / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:84 | / Backend version change / New entry, cache_hit=false, updated provenance / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:85 | / File bytes changed, PCM unchanged / Existing PCM entry reused; returned path/file hash updated / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:86 | / Damaged NPZ / Hash mismatch rejected, entry recomputed, next read hits / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:87 | / Determinism / Repeated JSON/NPZ export byte-equal; hydrated arrays identical / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:88 | / Core without neural modules / Separate process blocks torch/beat_this/allin1 imports and completes analysis / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:90 | Additional tests cover tiny/all-silent files, JSON model invariants, section-change | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:91 | localization, all-null section labels, fade-in, cache-root precedence, no-cache | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:92 | writes, CLI failures/multi-file export/clear, optional runtime fallback, and a mock | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:93 | Beat This! adapter verifying CPU/seed/no-DBN/return ordering without weights. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:95 | These are synthetic acceptance results, not evidence of real-corpus accuracy or | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:96 | listening quality. M4 corpus benchmarking and all later milestones remain untouched. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:100 | Command: `UV_CACHE_DIR="$PWD/.cache/uv" uv run python scripts/bench_analysis.py` | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:102 | The script generates 120 four-beat bars at 120 BPM (240.0 s stereo 44.1 kHz, A minor, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:103 | seed 41) in a temporary directory, then measures complete `analyze()` calls. Input | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:104 | generation is excluded; decoding, hashes, DSP and initial cache writes are included. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:105 | The first call is in a fresh Python process with the environment's existing compiled | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:106 | library caches; it is not a cold-install compilation benchmark. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:108 | / Operation / Wall seconds / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:110 | / First analysis, core backends, cache write included / 4.527434 / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:111 | / Warm analysis with use_cache=False / 3.101498 / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:112 | / Cache hit including file hashing and NPZ hydration / 0.056538 / | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:114 | Result: 120 BPM, 120 bars, 15 phrases. The measured first analysis is below the | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:115 | 20 s target. Host platform is macOS 27.2.1 arm64; `sysctl -n | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:116 | machdep.cpu.brand_string` was denied by the filesystem/process sandbox, so the exact | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:117 | Apple chip model was not independently verified and this is not labeled an M4 result. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:119 | Versions: numpy 2.5.5, scipy 1.18.1, librosa 1.0.1, pyloudnorm 0.2.0, soundfile | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:120 | 0.14.0, numba 0.68.1. Core backend/pipeline implementation versions are all `1`. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:121 | The JSON manifest records these versions; the cache directory suffix fingerprints | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:122 | the complete version dictionary and optional checkpoint content. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:126 | 1. Read architecture/rules/M0 evidence; inspect the uncommitted foundation and test | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:127 |    interfaces. No reset, checkout, commit or remote operations performed. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:128 | 2. `UV_CACHE_DIR="$PWD/.cache/uv" uv sync --dev`, then `uv sync --locked --dev` | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:129 |    — succeeded: 87 resolved packages (including optional/platform packages), 55 | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:130 |    core/dev distributions checked. Torch and models are absent from the core env. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:131 | 3. `uv run python scripts/gen_schema.py` with the same UV_CACHE_DIR — wrote both | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:132 |    schemas. Byte-equality checks pass, including M0's MixScript schema. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:133 | 4. Targeted `uv run pytest tests/test_analysis.py -m 'not slow' -q` runs checked | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:134 |    algorithm and edge cases during implementation. Early probes exposed a one-sample | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:135 |    falling-edge onset offset and short-file CQT padding warnings; both fixed. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:136 | 5. `uv run ruff check --fix ...`, `uv run ruff format ...`, `uv run pyright` — imports, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:137 |    formatting and strict typing normalized; no global typing/lint relaxations added. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:138 |    Explicit Any is restricted to upstream libraries without complete stubs and JSON | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:139 |    boundary decoding. Public backend interfaces and returned models are typed. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:140 | 6. `uv run mixconsole analyze .cache/m1/128.wav --cache-dir .cache/m1/cli-cache | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:141 |    --json .cache/m1/cli-analysis.json` — rich table showed 128 BPM, C major/8B, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:142 |    −24.1 LUFS, 16 bars, 2 phrases and 1 section. JSON + NPZ hydrated successfully. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:143 |    `uv run mixconsole cache info --cache-dir .cache/m1/cli-cache` reported 1 entry. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:144 |    These paths are ignored local generated artifacts, not source assets. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:145 | 7. `uv run pytest -m slow -q` — 1 skipped, 101 deselected; explicit skip reason: | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:146 |    `set MIXCONSOLE_BEAT_THIS_CHECKPOINT to an MIT checkpoint for model inference`. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:147 |    No claim of real-weight neural accuracy or runtime is made. The supplied adapter | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:148 |    and marked test are ready for a user-provided checkpoint and optional install. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:149 | 8. License review used upstream Beat This!/All-In-One docs, versioned PyPI metadata, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:150 |    and HTTP range reads of optional wheel license files. No implementation code was | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:151 |    copied. NVIDIA binary EULAs, NCCL BSD-3-Clause, NVTX Apache-2.0 and torch's bundled | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:152 |    license expression are recorded individually in `THIRD_PARTY.md`. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:153 | 9. Local scratch evidence: `.cache/m1/metrics.json`, `.cache/m1/benchmark.json`, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:154 |    `.cache/m1/slow.log`, `.cache/m1/licenses.json`, `.cache/m1/wheel-licenses.json`. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:155 |    Reproducible source evidence is in `tests/test_analysis.py` and | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:156 |    `scripts/bench_analysis.py`; all final measured metrics are preserved above. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:157 | 10. Final full check command/result below. Existing M0's 71 tests remain passing. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:159 | Contract details: large arrays remain in memory at `result.arrays` and are written | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:160 | only by caching or explicit export. JSON alone contains references; use | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:161 | `load_analysis()` to hydrate it. Bands use the shared 11.025 kHz spectrum; high-band | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:162 | power stops at 5512.5 Hz. Short-term windows use a finite floor and zero-padding; | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:163 | 4x true peak is an estimate. All-silent files have no beat grid/global BPM and null | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:164 | scalar loudness/peak. The fixed analysis seed is 0. Known-optional failures fall | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:165 | back with recorded actual versions. Multi-file exports include an aggregate JSON | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:166 | array plus individually loadable numbered JSON/NPZ pairs. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:168 | Atomic writes use same-directory temporary files, flush/fsync, then replacement; | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:169 | the JSON checksum is the pair's integrity record. A reader between the two replaces | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:170 | can miss and recompute; it cannot accept mismatched arrays. The cache does not promise | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:171 | a filesystem-wide transactional snapshot. Core numeric/library versions participate | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:172 | in invalidation. The file-hash index avoids repeated decoding of unchanged bytes. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:176 | Command: `scripts/check.sh > .cache/m1/final-check.log 2>&1` | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:178 | Exit status: **0**. Full command wall time: **15.792413 s** (target <90 s). | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:179 | Verbatim final output: | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:202 | The final run includes all 71 M0 tests and 30 M1 fast test cases. The one optional | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:203 | model test is intentionally deselected by the fast-check marker. No warnings, | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:204 | commits or remote changes. Local generated audio/NPZ scratch artifacts are ignored; | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |
| planning/M1-analysis.md:205 | no audio or model weights are present in the deliverable source tree. | verified | baseline scripts/check.sh; source/tests and dated milestone evidence |

### Schema, examples and CLI audit

| Surface / claims | Initial status | Evidence |
| --- | --- | --- |
| schemas/mixscript-v1.json: all field types, defaults, timing descriptions, extra-field prohibition | verified | test_committed_schema_matches + all tests/test_mixscript.py; structural schema does not enforce cross references. |
| schemas/track-analysis-v1.json: all model fields/descriptions and NPZ references | verified | tests/test_analysis.py schema equality, invariants, cache/export hydration. |
| examples/*.json: invented PCM hashes, tracks, automation, tempo/key intent | verified | both validate and round-trip; no render claimed. |
| CLI --help, --version, doctor, validate | verified | --help inspected; tests/test_cli.py passes including errors and missing optional dependencies. |
| CLI analyze --help: files, --json, --no-cache, --cache-dir, --beats, --sections | verified | tests/test_analysis.py CLI single/multi/export/failure; registry.py selects names. |
| CLI cache info/clear --help | verified | cache tests check recognized files and preservation of unrelated files. |
| README shell quickstart requires user's song.wav/a.wav/b.flac | verified | illustrative block, cannot run without input; add separately marked runnable synthetic examples. |
| README Python example | not yet true | Will mark and execute in isolated temp directory through docs tests. |
| Future CLI mix/render/set/models, HTTP jobs and generated TS | not yet true | PLAN design only; not exposed in current --help. |

## Implementation and validation

The dated implementation notes below are retained as historical evidence. The
final current-tree results and follow-ups appear at the end of this file.

## Earlier implementation session (2026-11-18, 02:50–03:20 IST)

Done here (Continuation: do not redo; extend only where a gap is real):

| Area | What | Evidence |
| --- | --- | --- |
| Repair | Interrupted v1.1 edit: `Explanation` used before definition (import error), untyped `candidates` default, long lines | package imports; check.sh green |
| B. MixScript v1.1 | `PlayRegion` alias bug fixed (aliases `in`/`out` broke dump→load round-trip; now `in_seconds`/`out_seconds`); `load_mixscript(upgrade_to_latest=)`, `dumps_mixscript` canonical JSON, `LATEST_VERSION`; `schemas/mixscript-v1.1.json`; examples migrated to v1.1 (v1 originals in `tests/fixtures/v1-*`); CLI `validate` now also reports malformed JSON cleanly | `tests/test_mixscript_v11.py` (12 tests), `tests/test_mixscript.py` |
| C. Service | `mixconsole.service`: `ProgressEvent`, `Progress`, `CancelToken`/`Cancelled`, `analyze_tracks(workers=…)` with process pool and input-order results; CLI `analyze --workers` + progress bar | `tests/test_service.py` (real 2-process pool included) |
| C. Config | `mixconsole.config`: defaults < TOML (`$MIXCONSOLE_CONFIG` or platform config dir) < `MIXCONSOLE_*` env, unknown keys rejected; `mixconsole config show`; `platformdirs` declared | `test_settings_precedence`, `test_config_show_cli` |
| C. Plugins | `registry.register`, `load_plugins()` from entry-point group `mixconsole.backends` (broken plugins logged + skipped), `mixconsole.families` reserved; pipeline version `analysis@2` | `test_plugins_register_and_skip_broken` |
| C. Logging | `--verbose/-v`, `--quiet/-q` configure stdlib logging | CLI |
| D. Bench | `mixconsole.bench` (metrics, results, perf, accuracy), `mixconsole bench perf|accuracy --compare`, `schemas/bench-result-v1.json`, `bench/results/LATEST.md`; compare treats real-time factor as higher-is-better and ignores sub-20 ms / sub-8 MiB jitter | `tests/test_bench.py` (13 tests incl. hand-computed F-measure, Acc1/Acc2, MIREX key score) |
| Perf | Loudness rewritten: filter once per channel, reduce to 100 ms blocks, BS.1770 gating in-house (matches pyloudnorm to 0.000 LU on 3 cases); float32 STFT; edge-cue temporaries trimmed | before/after below |

Perf before → after (Apple M4, synthetic, medians of 3):

| metric | before | after |
| --- | --- | --- |
| analyze 4 min cold | 2.40 s | 1.54 s (−36 %) |
| analyze 10 min cold | 6.93 s | 4.38 s (−37 %) |
| loudness 4 min | 1.37 s | 0.86 s |
| peak heap 4 min | 1057 MiB | 495 MiB (−53 %) |
| peak heap 10 min | 2643 MiB | 1237 MiB (−53 %) |
| process max RSS (whole bench) | 3763 MiB | 2350 MiB |

Accuracy (full synthetic sweep, unchanged by the perf work): tempo Acc1 100 % at clean/30/20/10 dB SNR over
56 tempos (70–180 BPM); beat F mean 1.00/1.00/1.00/0.98; downbeat F mean 1.00/1.00/0.98/0.94; 3/4 meter 100 %;
sections 100 % on homogeneous and breakdown cases; key exact 87.5 % (MIREX 0.90) at 20 dB.

Known limits found:
- Key: with synthetic drums, D/D#/G# minor read as parallel major (noise is irrelevant; no drums → 24/24).
  A CQT time-median (HPSS-lite) made it worse (4 wrong), so it was not adopted. Validate on real music (M1R part 2)
  before tuning further; don't overfit the synthetic drum kit.
- Peak memory still scales linearly (~1.2 GiB heap for 10 min); a 60-min mix needs chunked features (PLAN §7.10).

`scripts/check.sh`: **150 passed, 1 deselected**, ~22 s.

Still open for continuation in M1H: A (finish audit vs current tree), D dataset hooks, E (quality gates, supply chain incl.
NVIDIA EULA → CPU-only torch, CI jobs, dependabot, CodeQL, docs site + ADRs, frontend stubs).

## Resumed current-tree audit (2026-11-18)

This supersedes the initial inventory where the files have changed. The original
inventory records a historical baseline, not proof of the current tree. Existing
M1R, v1.1, service and benchmark implementations are retained.

| Current surface / claim | Status before resumed edits | Evidence and required action |
| --- | --- | --- |
| README analysis, v1.1 and bench commands | verified | Current `analysis`, `mixscript`, `bench` source and their tests; rerun baseline check recorded below. |
| README cache location is universally `~/.cache` | verified | `analysis/cache.py:cache_root` currently uses this literal default; config's claim of platform cache is wrong. |
| README neural extra safe for allowlist | not yet true | `uv.lock` contains NVIDIA CUDA EULA dependencies; replace Linux/Windows torch source with CPU index. |
| CONTRIBUTING schema regeneration only v1 | wrong | `scripts/gen_schema.py` already exports four schemas; document all. |
| AGENTS hard rules and future layout | verified | Policy, not claims of implemented rendering. No commits/remotes authorized. |
| PLAN current status/defaults/point ids/fixed config path | wrong | Existing actionable findings remain unfixed; correct while retaining future design. |
| ROADMAP M1H acceptance | not yet true | Dataset hooks, supply-chain/docs gates and final evidence missing. Other milestones remain targets. |
| THIRD_PARTY static license table | wrong | New platformdirs role and forthcoming dependencies need generated metadata, fail-closed allowlist and linkage evidence. |
| CHANGELOG v1.1, benchmark, M1R delivery | verified | Source files and corresponding tests exist; removed bench_analysis.py really absent. |
| M0/M1 evidence final test counts and benchmark | verified | Historical logs only, not current counts. Removed benchmark script reference needs supersession note. |
| M1R evidence and remaining real-music work | verified | `tests/test_robustness.py`; no real-music claims introduced. |
| Earlier M1H claim C complete | wrong | `config.py` uses BaseModel/custom env parsing, not pydantic-settings; `analyze` lacks stage progress/cancel; service defaults workers=1 and accepts nonpositive values. |
| C plugin entry points / CLI logging | verified | `registry.load_plugins`, runtime dummy plugin test, CLI --verbose/--quiet. |
| Schema docs and examples | verified | Four generated schemas, v1 fixtures and migrated v1.1 examples; equality/semantic tests. No generated reference page yet. |
| CLI --help root/analyze/cache/config/bench | verified | Commands match current cli.py; dataset help is not yet present. Final help snapshot will cover all commands. |
| CI/pre-commit/check gates | not yet true | ci.yml has unpinned actions and only check job; check.sh has no supply-chain/coverage/docs gates; pre-commit only lint/type hooks. |
| PLAN §8 benchmark output names | wrong | Actual names include kind to prevent perf/accuracy collision; document `<date>-<kind>-<sha>-<machine>.json`. |
| Frontend, HTTP jobs, SQLite, model manager, long-audio streaming | not yet true | Later milestones; M1H delivers docs/stubs only. |

Baseline command: `scripts/check.sh > /tmp/m1h-current-baseline.log 2>&1`.


## Current-tree verification before final edits (2026-11-21)

The resumed work below was inspected before changing implementation. Earlier line
inventories are historical and their generic evidence is not current verification.

| Claim / scope | Current status | Evidence / action |
| --- | --- | --- |
| C service, settings, progress/cancel implemented | verified by inspection; tests running | `service.py`, `progress.py`, `config.py`, `tests/test_service.py`; pydantic-settings and stage checkpoints now exist. |
| D public dataset hooks missing | wrong | Four YAML manifests, `bench/datasets.py`, CLI command and synthetic tests already exist; verify formats and rights against upstream documentation. |
| E check.sh passes | wrong | `/tmp/m1h-baseline.log`: lint, format, typing and schema pass; license metadata snapshot missing. |
| CPU torch removes all license-gate obstacles | wrong | `third_party.py --refresh`: CUDA packages gone, but current torch metadata includes BSL-1.0 outside requested allowlist. Resolve explicitly, never silently waive. |
| E docs/CI/frontend stubs absent | wrong | Files exist; strict docs build, pins, link/lint, package install and supply-chain checks still require verification. |
| Coverage floor measured | not yet true | Initial floor 80 is provisional; run full suite and set measured integer floor, minimum 80. |
| README current milestone/status; CONTRIBUTING generated artifacts | wrong | README still M1; CONTRIBUTING mentions only v1 schema and old gates. Update after implementation verification. |
| PLAN all defaults/current promises | wrong | Default beats are core, allin1 is a stub, points have order not IDs, config path is platform-specific, cache invalidation includes dependency versions, result names include kind. Keep future architecture aspirational. |
| M0/M1/M1R historical numbers | verified as historical evidence only | Preserve prior commands/results; add supersession note for removed benchmark and changed loudness implementation. |
| New benchmarks and final check evidence | not yet true | Rerun full requested perf and accuracy, record output and limits. |

## Final current-tree audit and delivery (2026-11-21 IST)

The earlier line inventory is a dated baseline. This table checks its claims against
the delivered tree; “not yet true” means a later milestone target, not a delivered
feature. No prior M0/M1/M1R source or evidence was reverted.

| Surface | Final status | Current evidence / correction |
| --- | --- | --- |
| README analysis, cache, CLI, MixScript, status | verified | `scripts/check.sh`; `tests/test_analysis.py`, `test_cli.py`, `test_mixscript_v11.py`; status now says M1H and links current docs/results. |
| CONTRIBUTING commands, generated artifacts | verified | `scripts/check.sh`, `scripts/gen_schema.py --check`, `third_party.py --check`; now names all four schemas and generated reference. |
| AGENTS hard rules and layout | verified policy / not yet true layout targets | No audio/weights from `rg --files`; plan/render/server/UI packages remain stubs or future scope. No commits/remotes performed. |
| PLAN §§3, 7, 8 current claims | verified after corrections | Default beat tracker, SoundFile/ffmpeg path, ordered points, platform config, result filename, dataset command and future targets corrected; `registry.py`, `io`, `config.py`, CLI help. |
| ROADMAP milestones | M0/M1/M1H verified; M2+ not yet true | 179 fast tests pass; planning/render/UI targets remain future acceptance criteria. |
| THIRD_PARTY and CHANGELOG | verified after generation/update | 116 locked distributions; offline `third_party.py --check`, `test_supply_chain.py`; CHANGELOG records M1H. |
| Historical planning/M0, M1, M1R | verified as historical only | Their old test counts and perf numbers are dated; `scripts/bench_analysis.py` was superseded by `mixconsole bench perf`. M1R real-corpus work is still open. |
| Earlier M1H claims of missing C/D/E | wrong then, corrected now | `service.py`, `config.py`, `progress.py`, dataset manifests/runner, CI/docs/stubs exist; tests cover service, config, datasets and supply-chain. |
| Four schemas, examples, generated reference | verified | `scripts/gen_schema.py --check`, schema tests, `mkdocs build --strict`; v1 files stay in fixtures. |
| CLI `--help` root, analyze, cache, config, bench and dataset | verified | `uv run mixconsole --help`, `uv run mixconsole bench dataset --help`; missing dataset prints instructions. Mix/render/set/models remain not yet true. |
| CI and frontend promises | files verified; hosted runs not yet true | Pinned action SHAs, jobs/workflows, dependabot, pre-commit and docs build inspected locally; `apps/console` and `packages/schema-ts` are README stubs, no UI/API/SQLite yet. |

Dataset manifest sources were checked against the upstream annotation repositories:
[Ballroom](https://github.com/CPJKU/BallroomAnnotations),
[GTZAN-Rhythm annotation mirror](https://github.com/CPJKU/beat_this_annotations/tree/main/gtzan/annotations/beats),
[GiantSteps Key](https://github.com/GiantSteps/giantsteps-key-dataset), and
[GiantSteps Tempo](https://github.com/GiantSteps/giantsteps-tempo-dataset).
Their audio is user-supplied and no public audio was available locally. The CLI
prints acquisition/layout instructions when files are absent; synthetic dataset
tests verify matching and hand-computed metrics. Rights are recorded cautiously in
each manifest; no download or redistribution is performed.

### Fresh benchmark results

Commands: `uv run mixconsole bench perf --durations 30,240,600 --repeat 3 --out bench/results`
and `uv run mixconsole bench accuracy --out bench/results`. Results:
`bench/results/2026-11-20-perf-nogit-arm.json`,
`bench/results/2026-11-20-accuracy-nogit-arm.json` and generated `LATEST.md`.
The run is on a 10-CPU, 16 GiB Darwin arm host (the sandbox did not expose the
processor brand); “nogit” reflects this uncommitted tree.

| Measure | Result | PLAN §5 / M1 target | Status |
| --- | ---: | ---: | --- |
| 30 s cold analysis | 0.248 s | no budget | measured |
| 240 s cold analysis | 2.142 s | ≤20 s | pass |
| 600 s cold analysis | 5.655 s | no budget | measured |
| 240 s cache hit | 0.0406 s | ≤0.2 s | pass |
| Process peak RSS | 2426 MiB | ≤4096 MiB | pass |
| 240 s Python/NumPy peak heap | 495 MiB | no budget | measured |
| Synthetic tempo Acc1 (clean/30/20/10 dB) | 1.00 each | no public accuracy budget | measured |
| Beat F mean (10 dB); downbeat F mean (10 dB) | 0.9845; 0.9409 | no public accuracy budget | measured |
| 24-key exact / MIREX style score (20 dB) | 0.875 / 0.900 | no public accuracy budget | measured |
| Phrase exact; 3/4 meter (20 dB) | 1.00; 1.00 | no public accuracy budget | measured |

All implemented analysis budgets pass. Stems and plan/render budgets cannot be
measured before later milestones. This synthetic run is not real-music validation.
The previous dated 240 s result was 1.537 s; the fresh run is 39% slower on this
host, so the comparison would flag a regression. Both are below the 20 s budget;
profile repeated quiet-machine runs before changing DSP code for this variance.

### Gates and supply chain

`scripts/third_party.py --refresh` generated `scripts/licenses/metadata.json` and
`THIRD_PARTY.md` from all 116 lock entries. `--check` now passes offline. The
Linux/Windows optional torch variant is CPU-only and there are no NVIDIA EULA
packages in the lock. Torch's metadata includes bundled BSL-1.0; this is a narrow,
documented exception for optional torch in `third_party.py` and `NOTICES.md`, beyond
the originally enumerated allowlist. Unknown licenses, versions and sources still
fail closed. Revisit this explicit exception if the allowlist must remain literal.

`uv export` plus `pip-audit --no-deps --disable-pip` reported **no known
vulnerabilities**. `uv run --group docs mkdocs build --strict` passed;
`npx markdownlint-cli2 'README.md' 'docs/**/*.md'` found zero issues.
`uv build` produced a 72 KiB wheel and 288 KiB sdist; a fresh isolated venv ran
`mixconsole --version` and `doctor`, and had no torch installed. The tarball
contains no audio/weights/cache files. Hosted CI and lychee have not run locally.

Final `time scripts/check.sh` after the coverage floor and documentation edits:
exit **0** in **53.725 s** (under the 120 s limit). Ruff check passed, 106 files
matched Ruff format, Pyright reported 0 errors/warnings, schema drift check passed,
and the third-party check accepted 116 lock distributions. Pytest reported **179
passed, 1 deselected** in 46.23 s. Coverage was **91.26%** with `fail_under = 91`
(measured value rounded down). No commits, staging or git remote operations occurred.

### Follow-ups

- Run the four public datasets with lawfully supplied audio/annotations and report
  per-backend accuracy before changing defaults.
- Investigate quiet-machine benchmark variance and chunk long-audio features when
  the 60-minute workload lands; no current PLAN §5 budget was missed.
- Validate hosted docs/link, supply-chain, build, CodeQL and nightly jobs on CI.
- Decide whether to amend the formal license allowlist for torch's BSL-1.0 component
  or move neural dependencies to a separately reviewed plugin.
