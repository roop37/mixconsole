#!/usr/bin/env bash
# Web console checks (kept out of check.sh so the Python gate stays under 60 s).
# Usage: scripts/check-ui.sh [--no-e2e]
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.cache/uv}"
# pnpm is pinned by "packageManager" in package.json (corepack); `corepack enable` once if missing.
run_pnpm() { pnpm "$@"; }

run_pnpm install --frozen-lockfile
uv run python scripts/gen_api_types.py --check
run_pnpm --filter @mixconsole/console lint
run_pnpm --filter @mixconsole/console typecheck
run_pnpm --filter @mixconsole/console test
run_pnpm --filter @mixconsole/console build
if [[ "${1:-}" != "--no-e2e" ]]; then
  # Playwright drives `mixconsole serve --ui` with synthetic audio only.
  run_pnpm --filter @mixconsole/console exec playwright install chromium
  run_pnpm --filter @mixconsole/console e2e
fi
