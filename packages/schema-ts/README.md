# @mixconsole/schema-ts

TypeScript types for the MixConsole HTTP API. **Generated; do not edit.**

- `openapi.json`: the OpenAPI document exported from the FastAPI app (`mixconsole.server`).
- `src/api.d.ts`: `components` (one type per Pydantic model, also exported by name), `paths`
  and `operations` (path/query params, request body, responses per status).

```ts
import type { Job, Lanes, Schema } from "@mixconsole/schema-ts";
```

Regenerate after changing any route or model:

```
uv run python scripts/gen_api_types.py          # write both files
uv run python scripts/gen_api_types.py --check  # drift check (runs in scripts/check.sh and CI)
```

The emitter is a small Python translation of the OpenAPI 3.1 schema, so the drift check needs
no Node toolchain. When the console (M5) adds a pnpm workspace it can swap in `openapi-typescript`
against `openapi.json` without changing this package's contract. MixScript, TrackAnalysis and
benchmark JSON Schemas remain in `schemas/` (`scripts/gen_schema.py`); the API embeds the
MixScript document as an opaque object, so the UI validates edits through `POST /mixscripts`.
