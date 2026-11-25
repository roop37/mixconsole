# M1 — Analysis core

Status: complete for the core and optional adapter/stub delivery. Local validation:
macOS 27.2.1 arm64, Python 3.12.16, 2026-11-18. Beat This! real-weight inference is
conditional and was skipped locally; the adapter contract and fallback were tested.
M0 was already complete and uncommitted. Its foundation and evidence were preserved;
no commits, staging, remote changes, audio assets or model weights were added.

## Delivery checklist

- [x] Read `PLAN.md` (especially §3.1), `ROADMAP.md`, `AGENTS.md` and
  `planning/M0-foundation.md` before changing files. Work remained within M1.
- [x] `src/mixconsole/analysis/models.py`: finite Pydantic TrackAnalysis v1 contract,
  file/PCM SHA-256, timing, meter, tempo segments, bars, phrases, sections, key with
  three alternatives, loudness, per-bar energy, edges, null vocal activity,
  backend/dependency versions and fixed seed. Validators enforce musical order,
  downbeat/phrase membership, phrase bar indices and non-overlapping intervals.
- [x] `schemas/track-analysis-v1.json`, exported alongside the unchanged MixScript
  schema by `scripts/gen_schema.py`; byte-equality test for both schemas.
  Long short-term loudness and bar-energy arrays use typed sibling NPZ references.
- [x] Typed BeatBackend, KeyBackend, LoudnessBackend, SectionBackend and CueBackend
  Protocols in `analysis/interfaces.py`, with named registries and version provenance.
- [x] Core onset/DP beats: shared onset envelope, 70–180 BPM interval/autocorrelation
  prior, half/double resolution, librosa DP tracking, transient refinement,
  accent/low-band/harmonic bar phase for 4/4 or 3/4 and median-smoothed tempo maps.
- [x] Lazy CPU Beat This! adapter in `[neural]`, also included by `[all]`.
  `beat-this` and `torch` declared; local checkpoint hash recorded; fixed seed;
  no DBN/madmom. Missing optional dependencies/checkpoints and runtime failures
  warn and fall back. Unknown names fail instead of silently accepting typos.
- [x] Original CQT key-profile ensemble (Krumhansl–Kessler, Temperley and an original
  EDMA-style triadic profile), complete Camelot mapping, probabilistic alternatives.
- [x] Pyloudnorm integrated loudness; rolling 3 s K-weighted short-term power at
  10 Hz; chunked 4x polyphase true-peak estimate. Silence has null scalar LUFS/peak
  and a finite -120 LUFS curve floor. Forward windows are zero-padded at EOF.
- [x] Per-bar RMS/onset/low/mid/high spectral power; 4/8/16-bar phrase grid and
  offset chosen using attacks, energy change and chroma/MFCC novelty.
- [x] Original local self-similarity novelty with peak-picked sections and null
  labels. `allin1` is a reserved lazy stub, automatically falling back; NATTEN and
  upstream madmom installation caveats documented, with no package installed.
- [x] -60 dBFS head/tail gate, fade-in/out trends and hard-ending detection.
- [x] `analysis/cache.py`: PCM/version-addressed directories, environment/argument
  overrides, file-hash index, atomic temp/fsync/replace writes, JSON/NPZ pair
  integrity checks, corrupt-entry recomputation and explicit no-cache mode.
- [x] `mixconsole.analyze()` public API, rich multi-file CLI, JSON/NPZ export,
  `mixconsole cache info|clear`, updated doctor output and README quickstart.
- [x] Tests use session fixtures and temporary synthesized audio. The existing
  generator gained only an additive `phrase_offset_bars` option; existing M0
  defaults/annotations are unchanged. No recorded audio or learned weights used.
- [x] README, THIRD_PARTY.md, CHANGELOG.md and lockfile updated. Every new optional
  direct/transitive dependency and the optional weight family has license + URL.
- [x] Four-minute benchmark measured; final `scripts/check.sh` passed below.

## Accuracy evidence

`tests/test_analysis.py` uses a one-to-one temporal matcher (±70 ms) for F-measure,
so duplicate detections cannot inflate scores. Rhythm fixtures use 16 bars, seed
23, pad + bass + kicks/clicks and 8-bar crash markers. Phrase equality is exact
sample-aligned float equality, not a tolerance test. A measurement run using the
same fixture parameters produced:

| Ground-truth BPM | Estimated BPM | Beat F | Downbeat F | 8-bar phrase starts |
| --- | ---: | ---: | ---: | --- |
| 90 | 90.000000000 | 1.000 | 1.000 | exact |
| 100 | 100.000000000 | 1.000 | 1.000 | exact |
| 124 | 124.000000760 | 1.000 | 1.000 | exact |
| 128 | 128.000010207 | 1.000 | 1.000 | exact |
| 140 | 140.000000000 | 1.000 | 1.000 | exact |
| 174 | 173.999997218 | 1.000 | 1.000 | exact |

| Other acceptance metric | Measured result |
| --- | --- |
| Key tonic + mode, all 24 pad/bass keys | 24/24 (100%); requirement ≥90% |
| Camelot mapping | All 24 independently ordered wheel entries pass |
| Ramp 125 → 95 BPM | 8 tempo segments; first 123.125, last 97.108 BPM; beat/downbeat F=1.000 |
| Ramp 125 → 155 BPM | 8 tempo segments; first 126.873, last 152.895 BPM; beat/downbeat F=1.000 |
| Shifted phrase grids | Exact starts and lengths for 4 bars/offset 1, 8/offset 2, 16/offset 3 |
| 3/4 and monotonicity properties | 8 deterministic Hypothesis cases over 75–178 BPM, meter and head silence pass |
| Pink noise, normalized to −14 LUFS | −14.000000067 LUFS |
| Head silence, 0.31 s | 0.310000 s |
| Tail silence, 0.47 s after fade | 0.478163 s (8.2 ms error) |
| Fade-out / hard-ending distinction | Fade-out true, hard-ending false; abrupt cut separately detected |
| Short-term LUFS | First 3 s cross-checked against an independent 3 s block meter, <0.02 LU error |
| Cache hit | Below 0.2 s in acceptance test; 0.056538 s on full four-minute file |
| Backend version change | New entry, cache_hit=false, updated provenance |
| File bytes changed, PCM unchanged | Existing PCM entry reused; returned path/file hash updated |
| Damaged NPZ | Hash mismatch rejected, entry recomputed, next read hits |
| Determinism | Repeated JSON/NPZ export byte-equal; hydrated arrays identical |
| Core without neural modules | Separate process blocks torch/beat_this/allin1 imports and completes analysis |

Additional tests cover tiny/all-silent files, JSON model invariants, section-change
localization, all-null section labels, fade-in, cache-root precedence, no-cache
writes, CLI failures/multi-file export/clear, optional runtime fallback, and a mock
Beat This! adapter verifying CPU/seed/no-DBN/return ordering without weights.

These are synthetic acceptance results, not evidence of real-corpus accuracy or
listening quality. M4 corpus benchmarking and all later milestones remain untouched.

## Performance evidence

Historical M1 measurements below remain unchanged. M1H removed
`scripts/bench_analysis.py`; use `mixconsole bench perf` and `bench/results/LATEST.md`.
M1H also replaced integrated loudness reduction with in-house BS.1770 block gating
using pyloudnorm filters, verified against its meter. The current license inventory
uses optional CPU torch and excludes the earlier NVIDIA EULA dependencies.


Command: `UV_CACHE_DIR="$PWD/.cache/uv" uv run python scripts/bench_analysis.py`

The script generates 120 four-beat bars at 120 BPM (240.0 s stereo 44.1 kHz, A minor,
seed 41) in a temporary directory, then measures complete `analyze()` calls. Input
generation is excluded; decoding, hashes, DSP and initial cache writes are included.
The first call is in a fresh Python process with the environment's existing compiled
library caches; it is not a cold-install compilation benchmark.

| Operation | Wall seconds |
| --- | ---: |
| First analysis, core backends, cache write included | 4.527434 |
| Warm analysis with use_cache=False | 3.101498 |
| Cache hit including file hashing and NPZ hydration | 0.056538 |

Result: 120 BPM, 120 bars, 15 phrases. The measured first analysis is below the
20 s target. Host platform is macOS 27.2.1 arm64; `sysctl -n
machdep.cpu.brand_string` was denied by the filesystem/process sandbox, so the exact
Apple chip model was not independently verified and this is not labeled an M4 result.

Versions: numpy 2.5.5, scipy 1.18.1, librosa 1.0.1, pyloudnorm 0.2.0, soundfile
0.14.0, numba 0.68.1. Core backend/pipeline implementation versions are all `1`.
The JSON manifest records these versions; the cache directory suffix fingerprints
the complete version dictionary and optional checkpoint content.

## Commands, paths and limitations

1. Read architecture/rules/M0 evidence; inspect the uncommitted foundation and test
   interfaces. No reset, checkout, commit or remote operations performed.
2. `UV_CACHE_DIR="$PWD/.cache/uv" uv sync --dev`, then `uv sync --locked --dev`
   — succeeded: 87 resolved packages (including optional/platform packages), 55
   core/dev distributions checked. Torch and models are absent from the core env.
3. `uv run python scripts/gen_schema.py` with the same UV_CACHE_DIR — wrote both
   schemas. Byte-equality checks pass, including M0's MixScript schema.
4. Targeted `uv run pytest tests/test_analysis.py -m 'not slow' -q` runs checked
   algorithm and edge cases during implementation. Early probes exposed a one-sample
   falling-edge onset offset and short-file CQT padding warnings; both fixed.
5. `uv run ruff check --fix ...`, `uv run ruff format ...`, `uv run pyright` — imports,
   formatting and strict typing normalized; no global typing/lint relaxations added.
   Explicit Any is restricted to upstream libraries without complete stubs and JSON
   boundary decoding. Public backend interfaces and returned models are typed.
6. `uv run mixconsole analyze .cache/m1/128.wav --cache-dir .cache/m1/cli-cache
   --json .cache/m1/cli-analysis.json` — rich table showed 128 BPM, C major/8B,
   −24.1 LUFS, 16 bars, 2 phrases and 1 section. JSON + NPZ hydrated successfully.
   `uv run mixconsole cache info --cache-dir .cache/m1/cli-cache` reported 1 entry.
   These paths are ignored local generated artifacts, not source assets.
7. `uv run pytest -m slow -q` — 1 skipped, 101 deselected; explicit skip reason:
   `set MIXCONSOLE_BEAT_THIS_CHECKPOINT to an MIT checkpoint for model inference`.
   No claim of real-weight neural accuracy or runtime is made. The supplied adapter
   and marked test are ready for a user-provided checkpoint and optional install.
8. License review used upstream Beat This!/All-In-One docs, versioned PyPI metadata,
   and HTTP range reads of optional wheel license files. No implementation code was
   copied. NVIDIA binary EULAs, NCCL BSD-3-Clause, NVTX Apache-2.0 and torch's bundled
   license expression are recorded individually in `THIRD_PARTY.md`.
9. Local scratch evidence: `.cache/m1/metrics.json`, `.cache/m1/benchmark.json`,
   `.cache/m1/slow.log`, `.cache/m1/licenses.json`, `.cache/m1/wheel-licenses.json`.
   Reproducible source evidence is in `tests/test_analysis.py` and
   `scripts/bench_analysis.py`; all final measured metrics are preserved above.
10. Final full check command/result below. Existing M0's 71 tests remain passing.

Contract details: large arrays remain in memory at `result.arrays` and are written
only by caching or explicit export. JSON alone contains references; use
`load_analysis()` to hydrate it. Bands use the shared 11.025 kHz spectrum; high-band
power stops at 5512.5 Hz. Short-term windows use a finite floor and zero-padding;
4x true peak is an estimate. All-silent files have no beat grid/global BPM and null
scalar loudness/peak. The fixed analysis seed is 0. Known-optional failures fall
back with recorded actual versions. Multi-file exports include an aggregate JSON
array plus individually loadable numbered JSON/NPZ pairs.

Atomic writes use same-directory temporary files, flush/fsync, then replacement;
the JSON checksum is the pair's integrity record. A reader between the two replaces
can miss and recompute; it cannot accept mismatched arrays. The cache does not promise
a filesystem-wide transactional snapshot. Core numeric/library versions participate
in invalidation. The file-hash index avoids repeated decoding of unchanged bytes.

## Final check output

Command: `scripts/check.sh > .cache/m1/final-check.log 2>&1`

Exit status: **0**. Full command wall time: **15.792413 s** (target <90 s).
Verbatim final output:

```text
All checks passed!
71 files already formatted
0 errors, 0 warnings, 0 informations
============================= test session starts ==============================
platform darwin -- Python 3.12.16, pytest-9.2.0, pluggy-1.7.0
rootdir: <repo>
configfile: pyproject.toml
testpaths: tests
plugins: hypothesis-6.170.15, platformdirs-4.14.7
collected 102 items / 1 deselected / 101 selected

tests/test_analysis.py ..............................                    [ 29%]
tests/test_cli.py .........                                              [ 38%]
tests/test_io.py .................                                       [ 55%]
tests/test_mixscript.py ........................                         [ 79%]
tests/test_synth.py .....................                                [100%]

====================== 101 passed, 1 deselected in 13.17s ======================
```

The final run includes all 71 M0 tests and 30 M1 fast test cases. The one optional
model test is intentionally deselected by the fast-check marker. No warnings,
commits or remote changes. Local generated audio/NPZ scratch artifacts are ignored;
no audio or model weights are present in the deliverable source tree.
