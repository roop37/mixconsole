# MixConsole

The open, inspectable AutoMix for your own files. A local-first engine for automatic
DJ transitions, with editable, reproducible plans that explain each decision.

**Status: pre-alpha — M2 two-song mixing.** Analyze local tracks, rank transition
candidates, render a MixScript v1.1 and inspect a local HTML report. Benchmarks:
[bench/results/LATEST.md](bench/results/LATEST.md). The console UI is a later milestone.

## Quickstart

Install Python 3.12+ and [uv](https://docs.astral.sh/uv/), then from this checkout:

```sh
uv sync --dev
uv run mixconsole --version
uv run mixconsole doctor
uv run mixconsole analyze song.wav --json analysis.json
uv run mixconsole analyze a.wav b.flac --no-cache
uv run mixconsole mix a.wav b.wav -o out.wav --style auto --candidates 3
uv run mixconsole plan a.wav b.wav --json plan.mixscript.json
uv run mixconsole render plan.mixscript.json --track deck_a=a.wav --track deck_b=b.wav -o replay.wav
uv run mixconsole cache info
uv run mixconsole validate examples/trim-crossfade.mixscript.json
scripts/check.sh
```

SoundFile handles common audio formats. Install `ffmpeg` on your system for other
formats and multichannel downmixing (`brew install ffmpeg` on macOS or
`sudo apt install ffmpeg` on Ubuntu). It runs as an external process. Audio stays
on your machine; the core does not need torch, a GPU, or downloaded model weights.
The optional `neural` extra adds Beat This! and torch; `all` includes `neural`.
The uv project routes Linux/Windows torch to CPU wheels, excluding NVIDIA EULA
packages. This source routing does not apply to pip installs of neural extras.
The `stems` and `ui` extras remain placeholders.

<!-- test -->
```python
from mixconsole import analyze
from mixconsole.analysis.cache import save_analysis, load_analysis
from mixconsole.io import load_audio, write_audio
from mixconsole.testing.synth import generate_track

audio, truth = generate_track(bpm=120, bars=8, key="A minor", vocal_bars=(2, 5), seed=7)
write_audio("demo.wav", audio)
decoded = load_audio("demo.wav")
print(decoded.pcm_sha256, truth["phrase_starts"])
result = analyze("demo.wav", cache_dir=".cache/analysis")
print(result.global_bpm, result.key.camelot, result.loudness.integrated_lufs)
print(result.beats, result.phrases, result.cache_hit)
print(result.arrays["bar_energy"])
save_analysis(result, "demo.analysis.json")
restored = load_analysis("demo.analysis.json")
```

Internal audio is float32 stereo at 44.1 kHz. WAV output preserves float samples;
FLAC uses PCM24 and quantizes them. PCM identity hashes canonical little-endian
decoded samples; file identity hashes the original file bytes. Repeated I/O and
synthesis are deterministic with the same inputs and software environment.
Codec/library versions may change decoded PCM across environments.

## Two-song mix

`mixconsole mix A B -o out.wav` writes the rendered audio and an adjacent report
folder containing `plan.mixscript.json`, `report.json`, `report.html` and three
30-second previews. ffmpeg encodes Opus previews when available; WAV is the
fallback. `--style smooth|club|auto`, `--candidates N`, `--report-dir DIR` and
`--format wav|flac` control the result. `mixconsole plan` writes a shareable plan
without audio; `mixconsole render` checks canonical PCM hashes before replaying it.
`mixconsole bench transitions` runs the seeded synthetic pair suite with a plain
six-second linear crossfade baseline. No benchmark audio is committed.

The scorer is a heuristic, and verification thresholds catch measured seam issues;
these checks are not a listening test or a claim of superiority to another player.
Time-stretching uses the MIT-licensed Signalsmith binding in the core. Stems and
vocal separation remain M3 work, so those two family templates are unavailable.

## Analysis contract and backends

[`TrackAnalysis`](schemas/track-analysis-v1.json) stores file and canonical PCM hashes,
seconds-based timestamps, zero-based bar indices, tempo segments, top key alternatives,
structure and edge estimates, backend versions and analysis seed (zero). Tonic uses
pitch classes C=0 through B=11; mode is major/minor. Meter is 3 or 4 quarter notes.
Phrase lengths are 4/8/16 bars; a final phrase/bar may be truncated at EOF. Section
labels and vocal activity are null in M1. Key estimates on silence have low confidence;
beatless signals have no BPM or bars. Synthetic results do not establish real-music accuracy.

`result.arrays["short_term_lufs"]` is a 10 Hz curve of forward-looking 3 s K-weighted
windows, padded with silence at EOF. Silence uses a -120 LUFS floor in this numeric
array; integrated loudness and peak are null for digital silence. True peak uses
4x polyphase oversampling and is an estimate, not a certified BS.1770 meter.
`result.arrays["bar_energy"]` has columns RMS, onset strength, low (<150 Hz), mid
(150–2000 Hz), and high (>2000 Hz). Band energy uses the shared 11.025 kHz analysis
spectrum, so the high band ends at 5512.5 Hz. Spectral energies are relative STFT
power, not calibrated loudness. JSON has typed NPZ references (key, shape, columns);
`save_analysis`/`load_analysis` write and hydrate the sibling NPZ with an integrity hash.
Single-file CLI export writes an object; multi-file export writes an array plus
numbered individual JSON/NPZ pairs. Keep the NPZ siblings with exported JSON.

The defaults are `librosa` beats, in-house `profiles` key estimation, `pyloudnorm`
loudness (in-house block gating with pyloudnorm filters), in-house `novelty` sections and `edges` cues. Tempo comes from a
comb-filtered autocorrelation of the onset envelope with a metrical-level choice
(half/double/⅔/1½) under a 70–180 BPM prior; an in-house dynamic-programming tracker
locks beats to that period, the grid continues through beatless breakdowns, and
transients refine timing on clean material. Bar phase uses accent, low-band and
harmonic change (3/4 or 4/4); tempo segments come from least-squares beat fits.
Sections start on the 4-bar grid where timbre or band energy changes. Key scoring ensembles Krumhansl–Kessler, Temperley
and an original EDMA-style triadic profile. Phrases align 4/8/16-bar grids to changes
in energy, harmonic novelty and broadband attacks. These are estimates; uncertain
or atypical meter/tempo, rubato and percussion-free music need later corpus evaluation.

Select backends with `analyze(path, backends={"beats": "beat_this"})` or
`mixconsole analyze song.wav --beats beat_this`. Install `uv sync --extra neural`
and set `MIXCONSOLE_BEAT_THIS_CHECKPOINT` to a local, trusted official MIT checkpoint.
The adapter hashes the checkpoint into cache provenance, uses CPU inference with a
fixed seed and disables DBN processing. It does not download weights automatically.
Unavailable packages/checkpoints or optional runtime failures log a warning and
fall back; unknown backend names fail clearly. See the
[official Beat This! model instructions](https://github.com/CPJKU/beat_this#available-models).

`--sections allin1` reserves an optional **stub** and falls back to novelty. It is not
installed by any extra: All-In-One needs a compatible NATTEN build and its upstream
pipeline has madmom dependencies. NATTEN support/build requirements vary by torch,
CUDA and platform, particularly on macOS. See the
[upstream installation notes](https://github.com/mir-aidj/all-in-one#installation).
No madmom code or models are used by MixConsole.

Cache entries live under `~/.cache/mixconsole/<pcm_sha256>/<backend>@<version-key>/`.
The version key fingerprints all selected backend versions, numerical dependency
versions and optional checkpoint content. An auxiliary file-hash index avoids
re-decoding on hits; changing file bytes rechecks PCM identity. JSON and NPZ writes
are atomic, and their hash pairing detects interrupted writes. Corrupt entries are
recomputed. `MIXCONSOLE_CACHE_DIR`, `cache_dir=...` or CLI `--cache-dir` override the
root. `use_cache=False` / `--no-cache` bypass all cache reads and writes; explicit
JSON export still writes its requested files. `mixconsole cache info` reports entry
count/bytes; `mixconsole cache clear` removes recognized analysis entries and the
file-hash index while preserving unrelated files.

`mixconsole bench perf` times every analysis stage (30 s / 4 min / 10 min inputs by
default) and `mixconsole bench accuracy` scores tempo, beats, downbeats, meter, key and
sections on synthetic audio with noise. Both write a `bench-result/v1` JSON with a
machine fingerprint to `bench/results/` and regenerate `LATEST.md`; `--compare old.json`
flags > 20 % slowdowns. Fast tests reuse session fixtures;
`uv run pytest -m slow` runs optional Beat This! inference when its package and local
checkpoint are present. It skips with a reason otherwise.

## Service, configuration and datasets

The CLI calls `mixconsole.service.analyze_tracks(paths, progress=..., cancel=...,
workers=...)`. Results retain input order. Workers default to min(4, CPU count),
with a cap of 32; cancellation is cooperative at analysis-stage boundaries.
Inline progress reports stages; pooled progress reports completed tracks.

`mixconsole config show` reports validated settings loaded from platformdirs user
config `config.toml` (or `MIXCONSOLE_CONFIG`), then overridden by `MIXCONSOLE_*`
environment variables. Explicit service/CLI options take precedence. Configure
`cache_dir`, `workers`, `backends`, `max_stretch`, planner search bounds and verification thresholds. `offline`
reserves downloader policy; current analysis never downloads models.
`--verbose` / `--quiet` control stdlib logging. Backend plugins use Python entry
points in `mixconsole.backends`; `mixconsole.families` registers M2 transition family plugins.

`mixconsole bench dataset ballroom --audio-dir /path/to/audio` evaluates locally
supplied audio and annotations, or prints instructions. Also supported:
`gtzan_rhythm`, `giantsteps_key`, `giantsteps_tempo`. The
[dataset manifests](bench/datasets/ballroom.yaml) describe formats and rights;
no dataset audio or annotations are bundled or fetched automatically.

Developer checks include coverage, runnable docs, generated-schema drift and an
offline license allowlist. CI also defines link/lint, vulnerability, wheel-install,
CodeQL and nightly benchmark jobs. Hosted CI results are not yet available.
The [docs quickstart](docs/quickstart.md) describes local docs builds.

## MixScript v1.1

The [v1.1 schema](schemas/mixscript-v1.1.json) and [examples](examples/) describe tracks
by PCM SHA-256 rather than paths. Examples contain invented hashes and no music.
`uv run python scripts/gen_schema.py` regenerates the committed schemas (MixScript v1
and v1.1, TrackAnalysis, bench results).

v1.1 adds what an editor needs: stable `id`s on transitions, automation lanes and
effects (unique across the script, including track ids); a per-transition
`explanation` (reason, score breakdown, rejected candidates) and `candidates`
(auditionable alternatives); `locks` naming fields or lane ids the planner must not
change; an optional per-track `play` region (`in_seconds`/`out_seconds`); and
namespaced `extensions` (e.g. `"ui.colors"`) that the engine ignores but preserves.
v1 files still validate; `load_mixscript(path, upgrade_to_latest=True)` or
`mixconsole.mixscript.upgrade(data)` migrate them deterministically.
`dumps_mixscript` writes canonical JSON (sorted keys, defaults omitted).

Track IDs are keys in `tracks`; transitions reference these IDs. `duration` and cue
`seconds` use seconds. Cue `beat` positions are zero-based source quarter notes.
Automation and tempo-map beats are relative to the transition start on
`tempo.reference_track`'s quarter-note grid. Tempo interpolates linearly in beat
position between map points; an empty map records intent only. `beats_per_bar`
specifies quarter notes per reference bar. Gain and delay send use linear amplitude,
EQ uses dB, and filter frequencies use Hz. A point's curve controls the segment to
the next point. Effect parameters are named scalars; no effects execute yet.
Stem/pitch strategies describe intent; feasibility checks belong to later planners.

Pydantic validation also checks track references, cue bounds, ordering and lane
uniqueness. JSON Schema expresses structural constraints; use `mixconsole validate`
for the full contract. Unknown fields and non-finite numbers are rejected.

## Direction and contributing

See [ROADMAP.md](ROADMAP.md) for milestones, [PLAN.md](PLAN.md) for architecture,
and [CONTRIBUTING.md](CONTRIBUTING.md) for development practices. Milestone evidence
is in [planning/M0-foundation.md](planning/M0-foundation.md) and
[planning/M1-analysis.md](planning/M1-analysis.md), with hardening evidence in
[planning/M1H-hardening.md](planning/M1H-hardening.md).

**Honesty:** DJ-quality transitions are the goal, not a current capability. There are no
published listening results yet. We make no claim of outperforming Apple AutoMix,
djay, or any other system without published blind listening tests.

Licensed under the [MIT License](LICENSE). Dependencies retain their own licenses;
see [THIRD_PARTY.md](THIRD_PARTY.md). Do not contribute commercial audio or weights.
