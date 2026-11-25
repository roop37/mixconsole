#!/usr/bin/env bash
# Optional external baseline: VertexSelection/automix-engine (LGPL-2.1).
# Cloned and installed into its own venv under the MixConsole cache; it is only ever run as a
# separate process by `mixconsole bench corpus --systems ...,automix_engine`. Never imported,
# never vendored. Gives up after 15 minutes (see planning/M4-bench.md).
set -euo pipefail
ROOT="${MIXCONSOLE_CACHE_DIR:-$HOME/.cache/mixconsole}/external/automix-engine"
mkdir -p "$ROOT"
cd "$ROOT"
[ -d src/.git ] || git clone --depth 1 https://github.com/VertexSelection/automix-engine src
cd src
uv venv --python 3.12 "$ROOT/venv"
# 15 minute hard limit for the whole dependency install.
timeout 900 uv pip install --python "$ROOT/venv/bin/python" -r requirements.txt
echo "ok" > "$ROOT/READY"
