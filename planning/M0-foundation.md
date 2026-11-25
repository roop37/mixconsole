# M0 — Foundation

Status: complete. Local validation: macOS arm64, Python 3.12.16, 2026-11-18.

## Delivery checklist

- [x] Read `PLAN.md`, `ROADMAP.md`, and `AGENTS.md` fully before changes; M0 only.
- [x] `pyproject.toml`: uv project, Python >=3.12, Apache-2.0, src package, typed
  marker, Typer entry point, requested core/dev dependencies, and four empty extras.
  `uv.lock` records the resolved environment; `.python-version` selects 3.12 locally.
- [x] Package directories follow `AGENTS.md`; future analysis/planning/scoring/
  rendering/verification/reporting modules contain only docstrings. `bench/` and
  `ui/` document their future milestones. The scorer weight file is empty.
- [x] Executable `scripts/check.sh`: ruff check, format check, strict core pyright,
  and `pytest -m "not slow"`, stopping on a failing command.
- [x] `src/mixconsole/mixscript/`: v1 models, full validation, stable schema export,
  provenance, explanation/rejected candidates, track/stem automation, tempo map,
  cue positions, key strategy and effects. `scripts/gen_schema.py` regenerates
  `schemas/mixscript-v1.json`; tests compare the committed schema byte for byte.
- [x] Two validated illustrative plans in `examples/`: trim crossfade and stem
  handoff. Invented hashes do not refer to recordings. Examples do not claim to
  have been analyzed or rendered.
- [x] `src/mixconsole/testing/synth.py`, re-exported by `tests/synth.py`: stereo
  float32 44.1 kHz clicks/kicks, downbeat accents, seeded phrase crashes, root bass,
  major/minor pads, voiced formant-like bursts, silence, and a tempo ramp. Returned
  annotations include sample-aligned beats/downbeats/phrases/key/vocal intervals.
- [x] `src/mixconsole/io/`: SoundFile decode, scipy polyphase resampling, mono to
  stereo, optional ffmpeg decode/downmix, canonical PCM SHA-256 and file SHA-256,
  float WAV and PCM24 FLAC writing, invalid audio rejection.
- [x] CLI version, doctor and validate commands. Doctor shows Python, ffmpeg,
  placeholder extras, optional package versions, torch, MPS and CUDA availability.
- [x] README, contributing guide, Code of Conduct, security policy, full Apache-2.0
  license, changelog, dependency/license registry, three issue templates and the
  required six-section PR template.
- [x] Ubuntu/macOS CI matrix (Python 3.12/3.13), uv locked install, ffmpeg, check.sh;
  local pre-commit hooks; ignore rules for caches, environments, audio, output and
  model weights. Audio fixtures are generated in temporary test directories.
- [x] No added torch/model dependency, audio asset, model weight, or copied
  GPL/LGPL/AGPL source code. No commits or remote changes performed.
- [x] Final `scripts/check.sh` output recorded below.

## Decisions and contract details

Tracks are keyed by portable IDs and carry canonical PCM hashes rather than file
paths. Cue beats are source quarter-note positions; automation and tempo-map beats
are relative to the transition start on its reference track. `beats_per_bar` is in
quarter notes. Gain/send values are linear amplitude, EQ is dB, and filters are Hz.
Effects describe scalar parameters only; no rendering is implemented in M0.

Pydantic forbids unknown fields and non-finite numeric values and checks references,
cue bounds, strictly ordered maps/lanes, unique target/parameter lanes, and valid
strategy values. JSON Schema supplies structural validation; full semantic checks
use `mixconsole validate`. Pitch/stem feasibility is future planner work.

Synthetic time signatures count denominator pulses, with BPM in quarter notes.
Ramp BPM is linear in quarter-note position and integrated analytically, then
rounded to actual sample indices. Vocal regions are half-open intervals. Random
noise uses a local seeded NumPy generator. Tests do not depend on recorded music.

WAV preserves float32 samples; FLAC quantizes to PCM24 and rejects out-of-range
input instead of silently clipping. PCM hashes are SHA-256 of C-order little-endian
float32 stereo samples at 44.1 kHz. Determinism is verified within the installed
software environment; codec/resampler changes can alter PCM across environments.

## Commands and results

1. `cat PLAN.md ROADMAP.md AGENTS.md` — read the full architecture, roadmap and rules.
   Initial `git status --short` showed only those three user-provided files untracked.
2. `UV_CACHE_DIR="$PWD/.cache/uv" UV_PYTHON_INSTALL_DIR="$PWD/.cache/python" uv sync --all-extras --dev`
   — succeeded; Python 3.12.16, 56 resolved packages including this project, 55
   installed distributions on macOS. The initial attempt without a local Python
   install directory hit the sandbox's home-directory write restriction; the local
   cache resolved it. These caches are ignored.
3. `UV_CACHE_DIR="$PWD/.cache/uv" uv run python scripts/gen_schema.py` — wrote
   `schemas/mixscript-v1.json`. Both examples validate and round-trip through models.
4. `UV_CACHE_DIR="$PWD/.cache/uv" uv run ruff check --fix .` and
   `UV_CACHE_DIR="$PWD/.cache/uv" uv run ruff format .` — normalized imports and
   formatting. Initial checks also found typing issues and adjacent-pair iteration
   warnings; corrected with typed factories and `itertools.pairwise`.
5. `scripts/check.sh` — initial test run found doctor interpreting bracketed extra
   names as Rich markup and a helper alias accidentally collected as a test.
   Both corrected. Subsequent run: **71 passed**, no warnings; pyright had zero errors.
6. `UV_CACHE_DIR="$PWD/.cache/uv" uv run mixconsole --version` — `mixconsole 0.0.1`.
7. `UV_CACHE_DIR="$PWD/.cache/uv" uv run mixconsole doctor` — Python 3.12.16;
   `/opt/homebrew/bin/ffmpeg` present; torch, Beat This!, Demucs and FastAPI absent;
   MPS/CUDA unavailable; all extras correctly identified as placeholders.
8. `UV_CACHE_DIR="$PWD/.cache/uv" uv run mixconsole validate examples/trim-crossfade.mixscript.json`
   and the same command for `examples/stem-handoff.mixscript.json` — both returned
   `Valid mixscript/v1: 2 tracks, 1 transitions` with exit status 0.
9. `UV_CACHE_DIR="$PWD/.cache/uv" uv build` — built the sdist and wheel in ignored
   `dist/`. Inspected archive entries with Python `tarfile`/`zipfile`: no cache,
   virtualenv or git internals included; wheel contains the testing kit and
   `py.typed`. Reviewed installed distribution metadata/license files for
   `THIRD_PARTY.md`, including all locked transitive packages and build dependencies.

Test evidence is in `tests/test_mixscript.py`, `tests/test_synth.py`,
`tests/test_io.py`, and `tests/test_cli.py`. Coverage includes deterministic WAV/FLAC
bytes, cross-container PCM hashes, mono resampling, real ffmpeg AAC fallback and
six-channel downmix, bad/missing input, no-torch imports, CLI failures, independent
constant/ramped timing calculations, non-4/4 signatures, vocal bounds, key spectrum,
seeded repeats, and deterministic Hypothesis cases. No tests were skipped locally.

CI configuration is supplied; hosted Ubuntu/macOS jobs were not executed in this
local session. Later milestones' analyze/mix/render/UI behavior remains unimplemented.

## Final check output

Command: `scripts/check.sh > .cache/m0-final-check.log 2>&1`

Exit status: **0**. Verbatim final output:

```text
All checks passed!
63 files already formatted
0 errors, 0 warnings, 0 informations
============================= test session starts ==============================
platform darwin -- Python 3.12.16, pytest-9.2.0, pluggy-1.7.0
rootdir: <repo>
configfile: pyproject.toml
testpaths: tests
plugins: hypothesis-6.170.15, platformdirs-4.14.7
collected 71 items

tests/test_cli.py .........                                              [ 12%]
tests/test_io.py .................                                       [ 36%]
tests/test_mixscript.py ........................                         [ 70%]
tests/test_synth.py .....................                                [100%]

============================== 71 passed in 1.78s ==============================
```

Final setup verification: `UV_CACHE_DIR="$PWD/.cache/uv" uv sync --locked --dev`
and `uv sync --locked --all-extras --dev` both succeeded (56 packages resolved,
55 installed distributions checked). Final archive inspection confirmed this
evidence file, THIRD_PARTY.md, schema and lockfile are in the source distribution,
with no cache/environment/git internals. The delivered source tree contains no
audio or model-weight files. All changes remain uncommitted; remotes were untouched.
