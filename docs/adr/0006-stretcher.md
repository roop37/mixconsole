# 0006: M2 time stretcher

Status: Accepted for M2.

## Context

Beatmatched blends need pitch-preserving duration changes, reproducible PCM and a
core install on macOS arm64 and Linux without torch. The renderer must keep GPL
code out of its process. Signalsmith Stretch's upstream C++ library and Gregorio
Andrea Giudici's Python binding are both MIT licensed. The published binding has
wheels for CPython 3.12 on macOS arm64 and Linux x86-64; `uv add
python-stretch>=0.3.1` installed the macOS arm64 wheel locally. An independent
fresh-object repeat produced identical float32 samples.

## Decision

Use `python-stretch==0.3.1` from the uv lock as the core stretcher. The
`Stretcher` protocol in `render/stretch.py` wraps it. MixScript stores exact
beat-warp frame pairs and the selected backend in `render.stretcher`; rendered B
beats are processed piecewise in one Signalsmith state. A post-overlap ramp
returns B toward its native tempo at two bars per percentage point. Output
length is explicitly quantized to frames. A saved plan is sufficient to repeat
this processing without re-analysis.

## Consequences

Native binding and DSP versions are part of the reproducibility environment.
The current ramp processes one source beat at a time; sparse material may reveal
boundaries, so seam verification and listening checks remain necessary. Rubber
Band remains an optional future subprocess backend only. No Rubber Band code is
linked or copied.

Sources: [Signalsmith Stretch](https://github.com/Signalsmith-Audio/signalsmith-stretch),
[python-stretch](https://github.com/gregogiudici/python-stretch/),
[PyPI release](https://pypi.org/project/python-stretch/0.3.1/).
