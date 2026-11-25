# Generated frontend types (M4.5 placeholder)

M1H exports MixScript v1/v1.1, TrackAnalysis v1 and benchmark-result v1 JSON Schemas
using `uv run python scripts/gen_schema.py`; Python tests reject schema drift.
There are no handwritten or generated TypeScript models yet.

When the HTTP API exists, export its OpenAPI schema, select and pin a compatible
OpenAPI-to-TypeScript generator, and generate this package in CI. Run generation
into a temporary directory and byte-compare outputs to detect drift. The React/Vite
console imports types from this package; Pydantic remains the authority. Preserve
namespaced extensions, ordered points and stable transition/lane/effect IDs.
