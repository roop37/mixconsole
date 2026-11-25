#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.cache/uv}"
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python scripts/gen_schema.py --check
uv run python scripts/third_party.py --check
uv run python scripts/gen_api_types.py --check
# Fast suite with an enforced coverage floor (R2 restored it at 85; M3 raises it to 91).
# xdist keeps the run well under 60 s on an M4; slow/model tests: uv run pytest -m slow --no-cov
uv run pytest -m "not slow" -q -n 4 --dist worksteal --cov-fail-under=91
