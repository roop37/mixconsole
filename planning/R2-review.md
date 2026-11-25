# R2 — Independent review of M1H, M1R, M2

Date: 2026-11-25. Started by Codex (usage-limited after 4 minutes, no edits), completed by Claude.

## Findings

| # | Severity | Where | Finding | Fix | Test |
|---|---|---|---|---|---|
| 1 | High | `scripts/check.sh` | M2F replaced the test step with `pytest --no-cov`, silently removing the coverage gate. Measured fast-suite coverage was 85.4 % while docs claimed 91 %. | Gate restored at the measured value (`--cov-fail-under=85`, now 85.87 %). Raising to 91 with renderer tests is assigned to M3. | `scripts/check.sh` |
| 2 | High | `verify/metrics.py` | `_drift` and `_low_overlap` returned `0.0` when nothing was measured, so reports showed perfect drift/overlap for unmeasured seams (e.g. echo/filter candidates in `output/m2-real/burna-wayne/report.json`). | Both return `None` ("not applicable/measurable"). A beatmatched seam with unmeasurable drift, or an overlapping seam without separated contributions, now **fails** instead of passing. Reports print `n/a`. | `tests/test_verify_unmeasured.py` (4 tests) |
| 3 | Medium | `bench/transitions.py` | The 6 s crossfade baseline had no inspection, so its bass overlap read 0 bars, which flattered the baseline. | Baseline now passes separated A/B contributions; overlap is measured. Aggregates skip `None`. | covered by `test_two_basslines_overlap_is_measured` |
| 4 | Medium (design) | `score/heuristic.py` | When key compatibility < 0.2 the prior forces echo_out/cut. Talibans II (8B) → No Letting Go (4A), only −2.7 %, therefore cuts instead of blending. Real-music key accuracy is unverified. | Kept (DJ-defensible). M3 adds a drums-only beatmatched handoff for key clashes and weights the rule by key confidence. | M3 brief item 10 |
| 6 | Medium | tests | Renderer family paths (filter, echo, beatmatch bass swap, gain/seam effects, correlated-signal crossfade), stretch edge cases/ramp and every planning constraint had no fast tests. | Added `tests/test_render_paths.py` (11) and `tests/test_constraints.py` (10), asserting audio properties. Coverage 85.87 % → 87.59 %; floor raised to 87. | new tests |
| 5 | Low | Codex sandbox | `uv run pytest -m slow` failed for Codex only because of uv-cache permissions and the coverage floor applied to a subset. With `--no-cov`, slow tests pass (4 passed, 1 skipped). | No code change; run slow tests with `--no-cov`. | — |

## Real pairs after the fixes (`output/r2-real/`, songs read-only from `local/test-audio`)

| Pair | Tempo | Chosen | Drift | Low-band overlap | Loudness dip / bump | True peak | Time |
|---|---|---|---|---|---|---|---|
| No Letting Go → No Games | −7 % | beatmatch_blend, 8 bars | 3.81 ms (measured) | 0.0 bars (measured) | 0.00 / 0.93 LU | −1.05 dBTP | 15 s |
| Talibans II → No Letting Go | −2.7 % | cut_on_downbeat | n/a | n/a | 0.00 / 0.04 LU | −1.05 dBTP | 14 s |
| No Letting Go → Get Busy edit | +28 % | cut_on_downbeat | n/a | n/a | 0.35 / 0.00 LU | −1.05 dBTP | 15 s |

## Not verified here
Cross-platform determinism, the slow Beat This! test (needs `MIXCONSOLE_BEAT_THIS_CHECKPOINT`), README quickstart commands end to end,
and listening quality (needs Roop's ears; mixes are in `output/r2-real/`).

## Final gate
`scripts/check.sh`: ruff, format, pyright, schema drift, licence check all green; 226 passed, 5 deselected; coverage 87.59 % ≥ 87.
