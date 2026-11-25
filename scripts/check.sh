#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.cache/uv}"
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python scripts/gen_schema.py --check
uv run python scripts/third_party.py --check
# Fast suite with an enforced coverage floor (R2 restored it; raised to 87 with renderer/constraint tests; M3 raises to 91).
uv run pytest -m "not slow" -q --cov-fail-under=87
