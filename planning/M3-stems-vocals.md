# M3 — Stems + vocals (2026-11-25/26)

Built on M2 at commit 7d14412 (changes are uncommitted for lead review).

## Completion checklist

- [x] 1. `stems` extra: Demucs 4.1.0 (MIT) with the `htdemucs` checkpoint `955717e8-8726e21a.th`,
  SHA-256 `8726e21a993978c7ba086d3872e7608d7d5bfca646ca4aca459ffda844faa8b4`, fetched by
  `mixconsole models fetch htdemucs` into `~/.cache/mixconsole/models/htdemucs/` (ignored cache,
  never in the repo). Licence (code and weights MIT, Meta Platforms) and hash are recorded in
  `scripts/licenses/NOTICES.md` (rendered into `THIRD_PARTY.md`) and in `analysis/model_manager.py`.
  Only the last and first <= 60 s of each track's music are separated; stems are cached per
  (PCM sha256, window frames, model version) under `<cache>/stems/`. CPU and Apple MPS work (and CUDA is
  selectable); time and RAM are recorded in the cache sidecar JSON and below.
- [x] 2. `TrackAnalysis.vocal_activity` (per bar, per beat, vocal spans, lyric gaps >= 300 ms, stem
  regions, confidence) and `TrackAnalysis.stems` (windows + checkpoint hash). Additive schema change
  (`schemas/track-analysis-v1.json` regenerated; the old `null` still validates). Without the extra a
  spectral heuristic (confidence 0.3) fills the same field.
- [x] 3. Families `stem_handoff` (classic and the key-clash `drums_only` variant) and
  `vocal_over_instrumental`, with the constraints: no two lead vocals for more than a beat, no two basslines
  for more than a bar, A's vocal leaves only at a lyric gap, B's vocal enters only at a vocal onset, acapella
  family only when keys are compatible and B's intro is vocal-free. Overlapping non-stem blends are also
  rejected when stem-grade vocals would collide.
- [x] 4. Verify: `vocal_overlap_seconds` and `bass_overlap_bars` are measured on the rendered, post-automation
  stems (`RenderInspection.stem_contributions`) and gate the seam (1 beat / 1 bar, both configurable).
- [x] 5. Renderer: per-stem gain lanes (`StemTarget`), B stems beat-warped like the mix, latency-compensated
  re-summing (`stems.compensate`, `stems.resum`), null test below -60 dB (it is exact to float precision
  because the Demucs residual is folded into `other`).
- [x] 6. Tests: oracle (ground-truth) stems built from the synthetic generator give exact vocal bars,
  no-overlap guarantees, key-clash and acapella cases; fallbacks when the extra is missing; model tests are
  `@pytest.mark.slow` (`tests/test_m3_slow.py`).
- [x] 7. The three real pairs re-run with stems (below).
- [x] 8. This file; `scripts/check.sh` 53 s wall on this M4 (see the caveat on load).
- [x] 9. Coverage floor raised to 91 % in `scripts/check.sh` (measured 92.87 %). Added a fast `tiny` grid
  to `run_accuracy` plus `tests/test_bench.py::test_tiny_accuracy_grid_...` (bench/accuracy.py 23 % -> ~99 %),
  the M3 suite (`tests/test_m3.py`, 28 tests) and a tiny-HDemucs test that runs the real
  `DemucsSeparator` code path without weights.
- [x] 10. Key-clash blends: with stems a `drums_only` handoff competes (drums overlap, bass/other/vocals
  never do). The clash rule is weighted by key reliability (below). Talibans II -> No Letting Go now blends.

## Design notes

- **Windows.** Fixed edge windows (the last / first 60 s of the music) instead of a window centred on each
  candidate: the stems are then independent of the partner, cacheable per track and shared by all
  candidates. A stem candidate must lie inside both windows (a transition of up to 16 bars fits when the
  tempo is above about 64 BPM). This deviates from "transition +- 16 bars" for tracks whose best cue is
  earlier than the last 60 s.
- **Residual.** `other = mix - drums - bass - vocals`, so stems always re-sum to the original; leakage
  therefore lives in `other`.
- **Vocal activity.** 10 ms mask from the vocal stem (RMS above max(-52 dBFS, p98-30 dB) and spectral
  flatness < 0.35, holes < 120 ms closed, islands < 100 ms dropped). Outside the stem windows the
  heuristic mask is used; the heuristic over-detects (about 60 of 66-84 bars flagged per real song) and is
  never used for hard constraints (`confidence >= 0.8` and `stem_regions` required).
- **Schedules** (beats are transition-relative; `stem_plan` effect records them). Classic: drums and other
  equal-power crossfade over the two bars around a bar-aligned bass swap (A bass reaches 0 exactly where B
  bass starts); A vocal ramps out 0.1 beat after a gap starts, B vocal ramps in at the first B onset >= 0.5
  beat later. `drums_only`: only the drums overlap; A's bass/other leave before B's arrive. Acapella: A's
  drums/bass/other leave in the first 2 bars, A's vocal rides until a lyric gap in the second half.
- **Scoring.** New `vocal_safety` feature (weights re-balanced, still sum to 1; scorer `heuristic@4`),
  stem priors, and the key-clash forcing rule weighted by `key_reliability` = (min key confidence - 1/24) /
  (0.25 - 1/24), clipped to [0, 1]. `Key.confidence` is a probability over 24 keys, so the real tracks here
  measure 0.06-0.15 (reliability 0.1-0.5) while a clean synthetic key is 0.28. Variant choice
  (`drums_only` when raw key compatibility < 0.5) deliberately ignores confidence: the safe variant costs
  little when the estimate is wrong.
- **Verification order.** `mix_pair` now verifies candidates in score order (shortlist previews still
  rendered), abandoning a family after four failed verifications. Before, the first passing *shortlisted*
  candidate won, which hid higher-scored stem handoffs at other cues. Gain repair now also covers stem families.
- **Dependencies.** `uv.lock` forks demucs 4.1's Intel-macOS pins (torch<2.3, numpy<2); `override-dependencies`
  in `pyproject.toml` keeps one resolution and excludes `lameenc` (LGPL-3.0 MP3 encoder) and `sphn` (no licence
  metadata), which MixConsole never imports (`demucs.apply`/`demucs.pretrained` only). The extra is therefore
  Apple Silicon / Linux / Windows. Dev dependency `pytest-xdist` (MIT) was added; `third_party.py --refresh`
  reviewed 131 distributions, with the alias `"MIT License" -> MIT`.

## Evidence

### Separation cost (htdemucs, one 60 s stereo window of a real song, `shifts=0`, overlap 0.25, split)

| Device | First call (incl. model load) | Warm call | Process peak RSS |
|---|---:|---:|---:|
| CPU (Apple M4) | 17.6 s | 17.2 s | 1.97 GB |
| MPS | 6.0 s | 4.5 s | 0.98 GB |

Command: `uv run python <scratch>/bench2.py {cpu,mps}` (calls `DemucsSeparator(device).separate` on
`wayne-wonder-no-letting-go.mp3[60 s:120 s]`; RSS is `ru_maxrss`). Per track that is two windows: about 9-12 s
on MPS, about 35 s on CPU. In the pipeline the cache sidecars recorded 4.4-10.0 s per window on MPS with the
analysis process at 1.1-1.8 GB peak. A cached analysis plus cached stems re-plans a pair in about 12-34 s
end to end including 13-21 render/verify attempts.

### Real pairs (read-only songs in `local/test-audio`, outputs in `output/m3-real/`, warm stems cache)

Command per pair: `uv run mixconsole mix A B -o output/m3-real/<pair>/mix.wav --report-dir output/m3-real/<pair>`;
the same with `MIXCONSOLE_STEMS=off` in `output/m3-real-nostems/` (new verification order, heuristic vocals).

| Pair | Key A / B (confidence) | Without stems | With stems: family, length | Drift | Dip / bump LU | Peak dBTP | Vocal overlap | Bass overlap | Time |
|---|---|---|---|---:|---|---:|---:|---:|---:|
| No Letting Go -> No Games | 4A (0.14) / 6A (0.06) | beatmatch_blend, 8 bars | **stem_handoff (drums_only), 8 bars** | 3.81 ms | 0.00 / 1.29 | -1.05 | 0.00 s | 0.00 bars | 33.9 s |
| Talibans II -> No Letting Go | 8B (0.15) / 4A (0.14) | cut_on_downbeat | **stem_handoff (drums_only), 8 bars** | 0.23 ms | 1.33 / 0.00 | -1.05 | 0.00 s | 0.00 bars | 24.2 s |
| No Letting Go -> Get Busy edit | 4A (0.14) / 4A* (0.09) | echo_out, 4 bars | echo_out, 4 bars (stems n/a: +28 % tempo, `no_sync`) | n/a | 0.64 / 0.00 | -1.05 | n/a | n/a | 21.1 s |

*Get Busy is read as 4A by the profile detector as well. Talibans -> No Letting Go is the R2 finding (key clash,
-2.7 % tempo): it now blends with a drums-only beatmatched handoff, key reliability 0.49, so the forcing rule
runs at half strength and `stem_handoff drums_only` competes at prior 1.0. Several other stem candidates for
that pair failed verification (beat-phase drift 9-16 ms at cues whose beat grids disagree); the planner
then took the passing 0.23 ms candidate. Real-music key accuracy is still unverified, so "clash" here means
"the detector says clash". Pair 1 is a mild clash (distance 2 on the Camelot wheel, compatibility 0.36), so it
also uses the `drums_only` variant instead of a full-band blend; it outranked `beatmatch_blend` 0.839 vs 0.820
and passed verification. These objective metrics are not a listening test;
mixes are in `output/m3-real/<pair>/mix.wav` for Roop's ears.

Vocal activity on the four real songs (stem windows 120 s each): 27 lyric gaps (median 1.2-3.2 s) for three
songs and 89 for No Games.

### Limits and open issues

- Demucs leakage (and the folded residual) is audible in the stems; a handoff can expose it, which no objective
  metric here measures. Listening review is needed before any quality claim.
- Stem families need a beatmatchable pair (<= 8 % tempo difference after half/double-time) and cues inside the
  two 60 s windows; Get Busy (+28 %) cannot use them.
- Vocal data outside the stem windows is a heuristic and never constrains planning; the non-stem blends are
  only rejected for vocal collisions when both transitions lie inside stem windows.
- Key confidence is poorly calibrated on real tracks (0.06-0.15); the reliability rescale is a first estimate.
- The beat-phase drift check can reject good-sounding stem candidates (grid errors of 9-16 ms); this is the same
  gate as M2.
- Intel macOS has no stems (demucs pins torch<2.3 there); `uv sync --extra stems` fetches torch (about 2 GB).
- Timing: the shared machine carried a load average of 5-13 from other sessions while I measured; unloaded
  `check.sh` was 45 s earlier in the milestone, and 53 s on the final run. xdist (`-n 4`) is what keeps it under
  60 s; with `-n 6` or more the run slowed down because of oversubscription.

## Commands and results

```text
uv sync --all-extras --all-groups
uv run python scripts/third_party.py --refresh   # 131 distributions
uv run python scripts/gen_schema.py              # schemas/docs regenerated; --check passes
uv run pytest -m slow --no-cov                   # 6 passed, 1 skipped (Beat This! checkpoint), 93.5 s
scripts/check.sh                                 # see below
```

Slow tests (`tests/test_m3_slow.py`, real htdemucs weights on synthetic audio): null test below -60 dB, no
invented vocal bars, and a full `mix_pair` with no vocal or bass overlap. The real model detects only some of
the synthetic buzz-voice bars (e.g. bars 6 and 10 of {4, 5, 6, 10}), which is why the slow test asserts "no
false bars, at least two found" rather than equality (the oracle tests assert equality).

Without the extra: `uv run --isolated --no-dev python <script>` (no demucs, no torch) plans and renders a pair
with `MIXCONSOLE_STEMS=auto`, chose echo_out and reported "stems unavailable: install the 'stems' extra and run
`mixconsole models fetch htdemucs`" for both stem families.

### Final `scripts/check.sh`

```text
All checks passed!                                  (ruff check)
124 files already formatted                         (ruff format --check)
0 errors, 0 warnings, 0 informations                (pyright, strict)
schemas/docs up to date                             (gen_schema.py --check)
Third-party licenses: 131 locked distributions OK
TOTAL                                           4026    287    93%
Required test coverage of 91% reached. Total coverage: 92.87%
255 passed in 46.63s            (pytest -m "not slow" -n 4 --dist worksteal)
real 52.97  user 170.31  sys 14.35
```

## M3.1 stems opt-in (2026-11-26)

Owner listening test: stem families won almost every blendable pair and real-song vocals sounded bad
(Demucs bleed / phasey vocals). Stems are now optional and must earn their place.

- **`stems` = `off` (default) | `auto` | `on`** (`Settings.stems`, `MIXCONSOLE_STEMS`, `mixconsole mix --stems`).
  `off`: both stem families are rejected with "stems disabled", analysis uses the heuristic vocal backend, no
  separation. `on`: M3 behaviour. `auto`: separation runs (measured vocals are needed to judge), then
  `plan.candidates._gate_stems` keeps stem candidates only if (a) key clash (compatibility < 0.2 with
  key reliability > 0) or a measured vocal collision rejected every beatmatch_blend/filter_sweep, AND (b) the best stem score
  beats the best plain candidate (beatmatch_blend, filter_sweep, echo_out, cut_on_downbeat, trim_crossfade)
  by `stems_auto_margin` (default 0.05). The decision text (allowed / declined and why) is appended to
  `Explanation.chosen_because`; declined families appear in the pruned list as `<family>_auto`.
- **Scoring:** the plain-vs-stem bias came from `vocal_safety` (stems 1.0, plain penalised by the over-detecting
  heuristic). Without stem-grade vocal data in the window the collision penalty is now halved (scorer
  `heuristic@5`). Stem priors unchanged (they only matter when stems are eligible).
- **Bleed check:** `verify.metrics.stem_leakage` = energy-weighted max |zero-lag correlation| of the vocal stem
  with drums/bass/other in 100 ms blocks (raw, warped stems of the handoff window, `RenderInspection.stem_sources`).
  Fails above `max_stem_leakage` (0.25, uncalibrated: no ground-truth separation of real songs exists here;
  tune from the reported values); None when unmeasurable. Residual energy lives in `other` (folded), so it is
  covered by that correlation.
- **Also fixed:** the gain-repaired re-verification skipped the vocal-overlap limit; it now applies it.
- **Tests:** `tests/test_stems_optin.py` (default off and no separation, CLI option, auto without clash -> plain,
  auto with clash + margin, vocal-collision reason, leaky synthetic stem fails, None when unmeasured).
  `scripts/check.sh` green (285 tests, coverage 93.0 %, 56 s).
- **Real pairs:** `output/m3fix-real/<pair>-default` and `-auto` (table in the lead's report; metrics in each
  `report/report.json`).
