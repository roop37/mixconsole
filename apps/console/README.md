# Console (M5 placeholder)

The future console uses React, Vite and TypeScript in a pnpm workspace. No UI code
or frontend dependencies are installed in M1H. M4.5 supplies the local FastAPI API,
HTTP artifact delivery, jobs and SSE progress; all engine work goes through
`mixconsole.service`. The UI edits versioned MixScripts and consumes analysis
lanes and preview artifacts. It does not import or reproduce DSP logic.

Types flow from Pydantic → JSON Schema (`scripts/gen_schema.py`) → M4.5 OpenAPI →
generated TypeScript in `packages/schema-ts`. The generator and API schema will be
pinned and CI will reject drift before the console is implemented. Types must not
be handwritten. Stable transition/lane/effect IDs support edits; point order is
preserved; locks constrain replanning. See `docs/adr/0005-frontend.md`.
