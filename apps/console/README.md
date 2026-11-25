# MixConsole web console

React 19 + Vite + TypeScript (strict), wavesurfer.js for waveforms, Biome, Vitest and Playwright.
It talks only to the local `mixconsole serve` API (token in the URL once, then `sessionStorage`) and
uses the types generated in `packages/schema-ts`; it never reproduces engine or DSP logic.

```sh
corepack enable && pnpm install                 # repo root, Node 20+
pnpm --dir apps/console build                   # -> apps/console/dist
uv run mixconsole serve --ui                    # serves the built app, prints the ?token= URL

# development with hot reload (API on 8765)
uv run mixconsole serve --port 8765 &
pnpm --dir apps/console dev                     # http://127.0.0.1:5173/?token=<token>

scripts/check-ui.sh            # lint, typecheck, Vitest, build, Playwright smoke (synthetic audio)
scripts/check-ui.sh --no-e2e   # without the browser test
```

Layout: `src/api` typed client and SSE, `src/lib` pure logic (snap, MixScript edits, history,
automation maths, report parsing, kit/votes, library sort; all unit-tested), `src/state.ts` reducer,
`src/actions.ts` side effects, `src/components` views, `e2e` Playwright smoke.
See [docs/console.md](../../docs/console.md).
