# M1R — Analysis robustness (part 1: tempo, beat grid, sections)

Status: part 1 done 2026-11-18 (tempo, beat grid, sections, regression suite).
Part 2 delivered 2026-11-21 with the limits recorded below.

## Bug found in review
M1 passed all of its own tests, which used clean synthetic audio only. With broadband noise added:

| bpm | SNR | M1 result | sections (expected 1) |
|---|---|---|---|
| 97 | 10 dB | 195.06 BPM | 11 |
| 97 | 2.5 dB | 198.63 BPM | 11 |
| 128 | 2.5 dB | 172.27 BPM | 8 |

Root causes:
1. Tempo was taken from gaps between raw waveform transients; noise creates spurious transients.
2. `librosa.beat.beat_track(bpm=…)` (librosa 1.0.1) did not hold the given tempo on noisy onset envelopes
   (asked for 90 BPM → beats at ~123 BPM).
3. Steady-tempo detection used per-beat tempo spread < 0.5 BPM, which frame-quantisation jitter breaks,
   so steady noisy tracks were split into fake tempo segments and global BPM was rounded.
4. Section peaks were thresholded relative to the track's own maximum, so homogeneous tracks
   were always split; beatless breakdowns had no bars at all, so they could not become sections.

## Changes
- `analysis/backends/beats.py` (backend version 1 → 2):
  - `estimate_tempo`: comb-filtered, unbiased autocorrelation of the detrended onset envelope, then a
    metrical-level choice among {¼, ⅓, ½, ⅔, 1, 1½, 2, 3, 4}× with a log-normal prior around 120 BPM,
    preferring the faster octave when its single-beat pulse is ≥ 0.8 of the slower one.
  - `track_beats`: in-house dynamic-programming beat tracker locked to that period (Ellis-2007 style),
    replacing `librosa.beat.beat_track`.
  - Transients are only used for sample-accurate snapping when they agree with the robust estimate
    (within 15 %, which keeps clean tempo ramps working), and snapping radius is 35 ms (was 80 ms).
  - `fill_gaps`: the beat grid continues through internal beatless regions (breakdowns), never into
    leading/trailing silence.
- `analysis/structure.py`:
  - `tempo_map`: steadiness from the residual of a least-squares beat-index fit (< min(20 ms, 10 % of a
    period)); varying tracks use 8-beat sliding least-squares local tempo.
  - `bar_sections`: boundaries only on the 4-bar grid, when timbral novelty ≥ 0.2 (absolute) or RMS/band
    energy changes ≥ 4.5 dB between the 4 bars before and after; -40 dB track-relative floor; bands with
    < 5 % of the band energy ignored; local-maximum rule. Falls back to frame-level novelty without bars.
- Section backend `novelty` version 1 → 2 (cache invalidation).
- Also fixed: the interrupted MixScript v1.1 edit (`Explanation` used before definition, untyped
  `candidates` default, two long lines) so the package imports again.

## Evidence (synthetic, SNR relative to track RMS)
Probe: `generate_track(bars=32, key="F# minor", seed=3)` + Gaussian noise, `analyze(use_cache=False)`.

| bpm | clean | 10 dB | 2.5 dB | −3.6 dB | beat F (−3.6 dB) |
|---|---|---|---|---|---|
| 90 | 90.00 | 90.00 | 90.00 | 90.02 | 0.91 |
| 97 | 97.00 | 97.05 | 97.08 | 97.07 | 0.92 |
| 124 | 124.00 | 124.02 | 124.02 | 124.03 | 0.96 |
| 128 | 128.00 | 128.02 | 128.10 | 128.02 | 0.96 |
| 140 | 140.00 | 140.01 | 140.03 | 140.02 | 0.96 |
| 174 | 174.00 | 174.00 | 174.40 | 174.00 | 0.95 |

3/4 at 110 BPM, 10 dB-ish noise: 110.05 BPM, meter 3, downbeat F 0.94.

Sections (bar index of each section start):

| case | clean | 30 dB | 20 dB | 10 dB |
|---|---|---|---|---|
| homogeneous (2 seeds) | [0] | [0] | [0] | [0] |
| drums → 8-bar drumless breakdown → drums | [0, 16, 24] | [0, 16, 24] | [0, 16, 24] | [0, 16, 24] |
| C major → F# minor at bar 16 | [0, 16] | [0, 16] | [0, 16] | [0, 16] |

Performance (Apple M4, core backends, no cache): 4-min track 2.69 s (M1: 4.53 s), 10-min track 7.02 s.
After the M1H memory work: 1.54 s and 4.38 s (see planning/M1H-hardening.md).

Regression suite: `tests/test_robustness.py` (tempo ±0.5 BPM + beat F ≥ 0.9 at 20 and 10 dB SNR for
90/97/124/140/174; downbeat F ≥ 0.85 at 20 dB; 3/4 meter; one section for homogeneous tracks;
breakdown and key-change boundaries; grid continues through the breakdown).

`scripts/check.sh`: ruff clean, format clean, pyright 0 errors, **117 passed, 1 deselected** in 23 s.

## Known limits
- Downbeat (bar phase) at 10 dB SNR is not reliable yet (124 BPM case: F < 0.85). Real music rarely has
  broadband noise at that level, but the bar-phase method (accent + low-band + harmonic change) should
  be revisited, or replaced by Beat This! downbeats when installed.
- Everything above is synthetic. Real-music behaviour is unmeasured until part 2.

## Part 2 scope
Creative Commons real-music sanity set, Beat This! checkpoint download + comparison table, degradation
suite (MP3 round-trip, compression, timing jitter, sparse percussion, no percussion) inside `mixconsole bench accuracy`.

## Part 2 execution (2026-11-21)

The seeded benchmark now covers white and pink noise at 30/20/10 dB SNR,
128 kb/s MP3 round-trip (ffmpeg), tanh dynamic-range compression, timing jitter
up to 10 ms, sparse kicks on beats 1 and 3, and pads plus bass without
percussion. The 32-bar fixture has an inserted eight-bar breakdown.
`tests/test_m1r_part2.py` exercises the degraded audio paths and checks the
no-percussion confidence and homogeneous section results. The earlier
`tests/test_robustness.py` remains intact.

One regression surfaced during this work: a compressed, otherwise homogeneous
128 BPM track had section starts at 0, 4 and 12 bars. The fixed novelty cutoff
was crossed by compressed phrase accents. `bar_sections` now requires novelty
above both the absolute cutoff and 1.5 times the track's 95th-percentile
novelty; the same track has one section. The section backend is `novelty@3` and
pipeline `analysis@3`, so cached analyses are invalidated. The original M1R
tempo, beat grid and gap-filling algorithms were not changed.

### Creative Commons sanity set

`bench/datasets/cc_sanity.yaml` lists 12 CC0 tracks with source URL, license,
artist and genre. None of their source pages states a human BPM, so BPM stays
unknown and no real-music accuracy score is claimed. `mixconsole bench dataset
cc_sanity --fetch` verified the source page's CC0 terms and downloaded all 12
tracks into `/tmp/mixconsole-m1r-cache/datasets/cc_sanity` (ignored cache,
not committed). Two initially listed ccMixter tracks were removed after their
source pages returned HTTP 403; their source BPM labels could not be verified
or used. Result artifacts:
`bench/results/2026-11-21-dataset-cc-sanity-nogit-arm.json` and
`bench/results/2026-11-21-dataset-cc-sanity-beat-this-nogit-arm.json`.

| Track | Genre | Core BPM / sections | Beat This! BPM / sections | Flag |
| --- | --- | ---: | ---: | --- |
| Shiva's Blossom | Indian / house | 135.0 / 6 | 135.0 / 8 | core confidence 0.04 |
| Funky Pop | synth pop | 121.0 / 3 | 120.8 / 2 | core confidence 0.07 |
| Rock and Roll | rockabilly | 150.0 / 1 | 150.0 / 1 | core confidence 0 |
| Punk | punk rock | 120.1 / 3 | 120.0 / 2 | core confidence 0 |
| FREE.99 | hip-hop vocal | 160.1 / 4 | 80.0 / 4 | octave ambiguity; core confidence 0 |
| Unwind | lo-fi hip-hop | 95.0 / 4 | 95.0 / 3 | core confidence 0.09 |
| Path | electronic dance | 119.5 / 5 | 119.5 / 6 | core confidence 0 |
| Dj Dance | house / EDM | 128.0 / 7 | 128.0 / 7 | core confidence 0 |
| Escape | rock | 135.0 / 3 | 134.9 / 3 | core confidence 0 |
| Open Up Your Eyes | acoustic folk | 79.1 / 2 | 139.5 / 2 | large tempo disagreement; core confidence 0 |
| Lucidity | techno / synth pop | 120.0 / 5 | 120.0 / 5 | core confidence 0 |
| Razor/Rock | piano rock | 128.0 / 7 | 128.0 / 7 | core confidence 0 |

The two tempo disagreements cannot be resolved without human annotation.
Core beat confidence is below 0.1 on every real track despite plausible BPM
estimates, so confidence is uncalibrated for real music. Beat This! currently
reports a fixed 0.8 when it finds beats; its confidence is also uncalibrated.
Section counts are descriptive because this set has no section annotations.

### Beat This! and backend choice

`UV_CACHE_DIR=$PWD/.cache/uv uv sync --extra neural --dev --offline` resolved
117 packages and checked 92 installed packages. `MIXCONSOLE_CACHE_DIR=/tmp/mixconsole-m1r-cache
.venv/bin/mixconsole models fetch beat_this` downloaded the official `final0`
checkpoint into the ignored cache and verified SHA-256
`8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331`.
Its URL, hash and MIT license are in `analysis/model_manager.py` and
`THIRD_PARTY.md`. Benchmark results identify `beat_this@1`, proving that
inference ran rather than falling back. Model tests remain marked `slow`.

The matched quick synthetic sweep uses 70–180 BPM in 10 BPM steps. Each
degradation below uses the same seeded signal with each backend; the full
70–180 BPM core sweep is reported separately below.

| Condition | Core Acc1 / Acc2 / beat F | Beat This! Acc1 / Acc2 / beat F |
| --- | ---: | ---: |
| Clean | 1.000 / 1.000 / 1.000 | 0.417 / 1.000 / 0.801 |
| White noise, 20 dB | 1.000 / 1.000 / 1.000 | 0.583 / 0.917 / 0.875 |
| Pink noise, 30 dB | 1.000 / 1.000 / 1.000 | 0.667 / 0.833 / 0.924 |
| Pink noise, 20 dB | 1.000 / 1.000 / 1.000 | 0.833 / 1.000 / 0.938 |
| Pink noise, 10 dB | 0.833 / 1.000 / 0.941 | 0.667 / 0.833 / 0.779 |
| Timing jitter | 1.000 / 1.000 / 1.000 | 0.667 / 1.000 / 0.883 |
| Sparse kicks | 0.667 / 1.000 / 0.884 | 0.500 / 1.000 / 0.827 |
| No percussion | 1.000 / 1.000 / 0.993 | 0.667 / 0.833 / 0.914 |
| MP3, 128 kb/s | 1.000 / 1.000 / 1.000 | 0.667 / 1.000 / 0.884 |

The core `librosa` backend remains the default based on this matched synthetic
comparison. These generated signals are unlike dense real music, and the CC
set has no beat labels, so a neural default is not justified by this evidence.
Sparse percussion still misses the Acc1 target (though Acc2 is 1.0), and
Beat This! misses the inserted-breakdown section test. The previously
documented 10 dB downbeat limit remains open.

### Full core accuracy and before/after

Command: `MIXCONSOLE_CACHE_DIR=/tmp/mixconsole-m1r-cache .venv/bin/mixconsole
bench accuracy --out bench/results`. Result:
`bench/results/2026-11-21-accuracy-nogit-arm.json`. This full sweep uses
56 tempos (70–180 BPM in 2 BPM steps) for each white-noise level; the other
conditions use six representative tempos. All outputs are from the seeded
synthetic fixture.

| Measure | Earlier M1 / pre-fix | M1R part 2 result | Target |
| --- | ---: | ---: | --- |
| 97 BPM noisy review case | 195.06 BPM | 97 BPM in part 1 probe | ±4% |
| Tempo Acc1/Acc2, white 20 dB, 56 tempos | 1.00 / 1.00 in M1H | 1.00 / 1.00 | ≥0.90 / ≥0.98 |
| Beat F mean, white 20 dB | 1.00 in M1H | 0.999 | ≥0.90 |
| Tempo Acc1/Acc2, white 10 dB | 1.00 / 1.00 in M1H | 1.00 / 1.00 | diagnostic |
| Homogeneous compressed track sections | 3 at 128 BPM before part 2 gate | 1 at 128 BPM | 1 |
| Homogeneous sections at white 20 dB | 1.00 rate in M1H | 1.00 rate | 1.00 |
| Inserted breakdown boundaries within one bar | 1.00 in M1H | 1.00 | 1.00 |
| CC sanity core section count, 12 tracks | 109 before relative gate | 50 after gate | no labels |

Pink-noise Acc1/Acc2 is 1.00/1.00 at both 30 and 20 dB across the six-tempo
subset; beat F mean is 1.00. At 10 dB, pink-noise Acc1 is 0.833, beat F is
0.941 and five of six homogeneous tracks remain one section (the 70 BPM case
splits). All six no-percussion tracks have mean reported beat confidence 0.035;
their Acc2 is 1.00. The CC section-count reduction is not a validated accuracy
gain without section annotations.

### Performance and result files

Command: `MIXCONSOLE_CACHE_DIR=/tmp/mixconsole-m1r-cache .venv/bin/mixconsole
bench perf --durations 30,240,600 --repeat 3 --out bench/results`.
Result: `bench/results/2026-11-21-perf-nogit-arm.json` on a 10-CPU,
16 GiB Darwin arm host. The comparison is to the same host's
`2026-11-20-perf-nogit-arm.json` (`analysis@2`); the new result uses
`analysis@3`. Medians of three:

| Measure | Before | After | Budget |
| --- | ---: | ---: | ---: |
| 30 s cold analysis | 0.248 s | 0.247 s | — |
| 240 s cold analysis | 2.142 s | 1.972 s | ≤20 s |
| 600 s cold analysis | 5.655 s | 5.428 s | — |
| 240 s cache hit | 0.041 s | 0.045 s | ≤0.2 s |
| 240 s Python/NumPy peak heap | 495 MiB | 495 MiB | — |
| Process peak RSS | 2426 MiB | 2523 MiB | ≤4096 MiB |

The small timing/RSS differences are within run-to-run variance and all
specified performance budgets pass. `bench/results/LATEST.md` now shows the
newest core and Beat This! accuracy and CC runs separately instead of hiding
one backend behind the other.

### Final validation

`time scripts/check.sh` exited 0 in **93.35 s** (under 120 s). Ruff check and
format passed for 109 files; Pyright reported zero errors/warnings; schema and
third-party metadata checks passed (116 locked distributions). Pytest reported
**192 passed, 1 deselected** in 89.26 s with **93.82%** coverage against the
91% floor. The added quick end-to-end benchmark test takes about 46 s and
checks the 20 dB targets, pink noise, section boundaries, no-percussion
confidence and MP3. Separately,
`MIXCONSOLE_BEAT_THIS_CHECKPOINT=/tmp/mixconsole-m1r-cache/models/beat_this/final0.ckpt
.venv/bin/pytest -q --no-cov -m slow tests/test_analysis.py::test_beat_this_local_checkpoint`
reported **1 passed** in 3.73 s. No audio or model weights were written to
the repository; no commits or remotes were used.
