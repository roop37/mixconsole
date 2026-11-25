# Benchmarks

`mixconsole bench accuracy` runs the seeded synthetic degradation suite; `--quick`
uses a coarser tempo grid. `mixconsole bench perf` measures cold analysis and cache
hits. These write JSON results and regenerate `results/LATEST.md`.
`mixconsole bench transitions` runs seeded two-song synthetic cases and a plain
six-second linear crossfade baseline. The result includes chosen-family pass rates,
drift, loudness dip and runtime; temporary audio is deleted after the run.

`mixconsole bench dataset cc_sanity --fetch` checks each track page's CC0 terms,
downloads the 12 reviewed tracks into the ignored MixConsole cache, and reports
tempo, key, sections, and confidence. The source pages do not provide BPM labels,
so these outputs are sanity checks rather than ground-truth accuracy scores.
Install the optional `neural` extra, run `mixconsole models fetch beat_this`, then
pass `--beats beat_this` to compare backends. Other public dataset manifests use
local audio and annotations supplied by the user.

No audio or model weights are stored here. See [ROADMAP.md](../ROADMAP.md).
