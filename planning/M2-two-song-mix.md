# M2 — Two-song mix v0.1 (2026-11-25)

## Completion checklist

- [x] Phrase/cue planner for gapless, cut, crossfade, beatmatch blend, filter sweep and echo; bounded scored candidates, locks and concrete rejection reasons.
- [x] Deterministic gain/EQ/filter/echo/stretch/limiter render, audio-derived seam verification, gain repair and safe fallback. Signalsmith Stretch is the MIT default.
- [x] `mixconsole mix` writes the chosen audio, MixScript, three local candidate previews, JSON and offline HTML report. HTML has inline waveform/beat/bar/phrase/section/cue SVGs, automation, score breakdown, rejection and verification details, and playable previews.
- [x] `mixconsole analyze FILE --html out.html` writes an offline viewer with the same waveform SVG, short-term LUFS, local `<audio>` and waveform click-to-seek.
- [x] Full synthetic transition benchmark, including a plain six-second linear crossfade baseline, saved in `bench/results/` and `LATEST.md`.
- [x] All three private real pairs rerun with current scoring; previews audited and stale unreferenced replay removed.
- [x] Fast gate under 60 seconds on this M4; full suite including slow tests in nightly CI.

## Synthetic transition benchmark

Command: `MIXCONSOLE_CACHE_DIR="$PWD/.cache/m2-bench-cache" UV_CACHE_DIR="$PWD/.cache/uv" uv run mixconsole bench transitions --out bench/results`.
Result: [`bench/results/2026-11-25-transitions-2660e3a-arm.json`](../bench/results/2026-11-25-transitions-2660e3a-arm.json); index: [`bench/results/LATEST.md`](../bench/results/LATEST.md). Ten seeded 32-bar pairs, all generated in a temporary directory. Values are means by selected family; time is end-to-end seconds per pair. Baseline time measures its own decode/crossfade/verify path and is not directly comparable to the planning pipeline.

| Family | Pairs | Length | Pass | Drift ms | Dip LU | Bump LU | Peak dBTP | Low-band overlap bars | Time s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| beatmatch_blend | 6 | 8 bars | 100% | 0.008 | 0.000 | 0.735 | -9.935 | 0.000 | 7.806 |
| cut_on_downbeat | 2 | 0 bars | 100% | 0.000 | 0.041 | 0.000 | -10.930 | 0.000 | 5.846 |
| echo_out | 2 | 4 bars | 100% | 0.000 | 0.442 | 0.000 | -10.117 | 0.363 | 7.290 |
| plain linear crossfade | 10 | 6 s | 10% | 0.000* | 2.140 | 0.000 | -10.708 | 0.000 | 0.853 |

*The baseline has no beat warp; zero reported drift does not mean its beats are aligned. Its nine failures are seam-threshold failures on this synthetic set. These objective metrics are not a listening-quality result.

## Private real pairs

Inputs are read-only files in `../../local/test-audio`; no source audio or weights are committed. Times below are warm-cache `/usr/bin/time -p` wall seconds for the full CLI mix. The old choices were read from the 2026-11-21 reports before rerendering. `auto` now targets 8 bars and `club` targets 8–16 via a 12-bar center; their length weights rose to 0.15 and 0.18 respectively. Phrase fit, energy, key/tempo safety and render verification still decide the result.

| Pair | Before | After family / length | Drift ms | Dip LU | Bump LU | Peak dBTP | Low-band overlap bars | Time s |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Burna → Wayne | beatmatch_blend, 4 bars | cut_on_downbeat, 0 bars | 0.000 | 0.000 | 0.039 | -1.050 | 0.000 | 9.90 |
| Wayne → Serani | beatmatch_blend, 4 bars | beatmatch_blend, 8 bars | 3.810 | 0.000 | 0.935 | -1.050 | 0.000 | 6.55 |
| Wayne → Sean | cut_on_downbeat, 0 bars | cut_on_downbeat, 0 bars | 0.000 | 0.345 | 0.000 | -1.050 | 0.000 | 5.10 |

All three pass verification and have three preview candidates. For Burna → Wayne, the ranked 4-bar echo had a 2.20 LU dip and the 8-bar filter sweep a 5.43 LU dip; verification selected the passing cut. For Wayne → Sean, the tempo gap favors a cut/echo rather than a long beatmatch. The scorer's 8–16-bar preference is conditional, not a promise of a long blend for every pair.

Output paths: `output/m2-real/{burna-wayne,wayne-serani,wayne-sean}.wav`, each corresponding `output/m2-real/<pair>/{plan.mixscript.json,report.json,report.html,preview-*.opus}`, and `output/m2-real/<pair>-plan.json`. Analysis viewer: `output/m2-real/wayne-analysis.html` (references its original MP3 path). These ignored outputs are local evidence. An audit of every `output/**/report.json` found every named preview present, zero unreferenced Opus/WAV previews, and no network URL in any report. Three old synthetic `preview-*.wav` files remain only because their current `output/m2-smoke/report/report.json` references them. The unreferenced `wayne-serani-replay.wav` was removed.

## Robustness and performance

`UV_CACHE_DIR="$PWD/.cache/uv" uv run pytest tests/test_robustness.py -q --no-cov`: 17 passed in 9.36 s. The original 16 parameterized cases are unchanged; the added 10 dB SNR, tanh-compressed homogeneous track stays one section. The existing `prominence=max(0.05, 0.2*curve.max())` therefore retains its absolute floor; no gate change was needed.

The dated 240 s synthetic cold analysis grew from 1.537 s (Nov 17) to 1.972 s (Nov 21). Stage medians changed: features 0.422→0.544 s, loudness 0.856→1.176 s, decode 0.078→0.106 s, beats 0.088→0.113 s. A fresh `cProfile` on a 240 s synthetic track took 2.046 s: feature extraction 0.909 s, loudness 0.832 s, of which true-peak `scipy.signal.resample_poly`/`upfirdn` used 0.747 s; cold lazy imports used 0.356 s. Thus true-peak oversampling and cold feature imports dominate current work, while the dated increase is spread across multiple stages. There is only one aggregate source commit, so a specific M1R code change cannot be isolated from host/dependency variance. No cheap change was made to the true-peak path without a matching accuracy comparison; 1.972 s remains far below the 20 s budget.

## Checks and limits

- `/usr/bin/time -p scripts/check.sh`: Ruff check passed, 113 files formatted, Pyright 0 errors/warnings, schema and 117 locked-distribution license checks passed, **201 passed, 5 deselected in 32.31 s; wall 40.17 s** on the M4. The gate runs `pytest -m "not slow" --no-cov`; `.github/workflows/bench.yml` runs the full pytest suite with coverage nightly, followed by perf, accuracy and transition benchmarks.
- `UV_CACHE_DIR="$PWD/.cache/uv" MIXCONSOLE_CACHE_DIR="$PWD/.cache/m2-slow" uv run pytest -m slow --no-cov -q`: **4 passed, 1 skipped** (optional Beat This! checkpoint absent), 57.61 s. This covers full render replay/hash equality, audio-derived drift, quick end-to-end transitions and quick accuracy targets.
- `UV_CACHE_DIR="$PWD/.cache/uv" MIXCONSOLE_CACHE_DIR="$PWD/.cache/m2-full" uv run pytest -q`: **205 passed, 1 skipped in 106.96 s; 91.63% coverage** (91% minimum). This is the full nightly pytest command.
- Viewer and fast mix smoke passed together (`2 passed in 4.56 s`). The fast gate includes a benchmark result-shape smoke and the dedicated slow set includes its full audio run.
- Private songs are only a three-pair functional check. No stems/vocal-safe handoff or blind-listening comparison is claimed in M2; subjective transition quality and broader genre coverage remain unmeasured.
