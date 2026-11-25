# Benchmarks

Run `mixconsole bench perf --durations 30,240,600 --repeat 3` and
`mixconsole bench accuracy` from the checkout. Both write text-only results under
`bench/results/`; `--compare old.json` displays percentage changes and flags perf
regressions above 20%, subject to timer/allocator noise floors. Input generation
is excluded from stage timings. Cold means bypassed analysis cache with numerical
libraries already initialized, not a cold operating-system file cache.

PLAN budgets for an Apple M4 with 16 GB RAM are ≤20 s for a four-minute track
without stems, ≤60 s with stems, ≤10 s for planning/rendering three cached
candidates, and ≤4 GiB peak RAM. Only core analysis is implemented. The additional
M1 warm-cache target is 0.2 s. Peak RSS is a process high-water mark including
benchmark setup; per-input Python/NumPy heap uses tracemalloc separately.

Accuracy covers 70–180 BPM in 2 BPM steps, white noise at clean/30/20/10 dB SNR,
3/4 and 4/4, all 24 keys, tempo ramps, phrase grids, soft compression and LUFS error
against pyloudnorm. Beat matching is one-to-one within ±70 ms; tempo Acc1 uses ±4%,
and Acc2 permits factors 1/3, 1/2, 1, 2 and 3. The MIREX-style key score is symmetric:
exact 1, fifth above/below 0.5, relative 0.3, parallel 0.2, otherwise 0.
See the [metric documentation](https://mir-evaluation.github.io/mir_eval/#module-mir_eval.key).

## Public datasets

`mixconsole bench dataset ballroom --audio-dir /path/to/audio --annotations-dir /path/to/labels`
evaluates local files, or prints acquisition instructions when directories are
absent. Names: `ballroom`, `gtzan_rhythm`, `giantsteps_key`, `giantsteps_tempo`.
Manifests in `bench/datasets/` identify sources, formats and rights. GTZAN uses the
CPJKU Beat This! annotation mirror of GTZAN-Rhythm. Preserve audio/annotation basenames.
For GiantSteps use `annotations/key` or `annotations_v2/tempo` as the annotation
root, retaining `.LOFI` in filenames. Zero BPM labels are excluded.

No audio or annotations are fetched or redistributed. Partial runs report excluded
labels and annotation hashes; duplicate audio basenames fail matching. Beat scoring
crops estimates to the annotated interval; tempo for beat-only sets is median IBI.
Scores are macro-averages over matched tracks, not a claim of full-corpus coverage.
No public corpus was available for the local M1H run.

## Latest measured results

{% include-markdown "../bench/results/LATEST.md" heading-offset=1 %}
