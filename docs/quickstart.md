# Quickstart

From the repository checkout, install Python 3.12+ and uv, then `uv sync --dev`.
The optional neural extra uses CPU inference and a user-provided checkpoint.
`uv sync --extra neural` selects CPU wheels on Linux/Windows via the uv project
index configuration. Core installs need no neural packages. The core wheel also
installs with pip; pip does not interpret uv's index routing for neural extras.

The following blocks run in isolated temporary directories during the docs tests.

<!-- test -->
```sh
mixconsole --version
mixconsole doctor
mixconsole config show
```

<!-- test -->
```python
from mixconsole.io import write_audio
from mixconsole.service import analyze_tracks
from mixconsole.testing.synth import generate_track

audio, _ = generate_track(bars=4, bpm=120, seed=7)
write_audio("demo.wav", audio)
results = analyze_tracks(["demo.wav"], workers=1, cache_dir="cache")
assert abs(results[0].global_bpm - 120) < 0.1
```

For your own files, use `mixconsole analyze song.wav --json analysis.json`.
Then run `mixconsole mix a.wav b.wav -o out.wav` for audio, a MixScript and a local
HTML report with three previews. `mixconsole plan a.wav b.wav --json plan.json`
plans without rendering. Replay with `mixconsole render plan.json --track
deck_a=a.wav --track deck_b=b.wav -o replay.wav`; canonical PCM hashes must match.
Keep JSON and its sibling NPZ together. For formats not supported by SoundFile,
install the system ffmpeg executable. `mixconsole analyze --help` lists options.

Configuration precedence is defaults, platform TOML, then `MIXCONSOLE_*` environment.
`MIXCONSOLE_CONFIG` overrides the config file path; `MIXCONSOLE_CACHE_DIR` overrides
cache storage. Workers default to min(4, CPU count), with a hard cap of 32.
`MIXCONSOLE_BACKENDS` accepts JSON; `MIXCONSOLE_BACKENDS__BEATS` and the legacy
`MIXCONSOLE_BACKEND_BEATS` select a backend. Explicit service/CLI arguments override
configuration. `offline` is reserved for a future downloader: analysis currently
never downloads weights. `max_stretch` bounds M2 tempo matching.

Use `--verbose` for diagnostic logging and `--quiet` for errors only. These flags
control logging, not command output. Service cancellation is cooperative between
analysis stages; a native DSP call finishes before its next cancellation check.

Developers run `scripts/check.sh`. To build the site locally:
`uv run --group docs mkdocs build --strict`. Runnable docs use an HTML `test` comment
marker immediately before a fenced `python` or `sh` block; unmarked examples may
require user-provided files. Each marked block runs independently with a 60 s limit.
