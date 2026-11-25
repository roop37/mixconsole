# 0005: React, Vite and generated TypeScript

Status: Accepted design; implementation deferred to M5.

## Context

An editable local console needs typed contracts and independent preview controls.

## Decision

Use React/Vite/TypeScript in apps/console. Generate types from Python schemas and OpenAPI into packages/schema-ts.

## Consequences

No UI code in M1H. Generator selection and drift gates accompany the M4.5 API; no handwritten API type duplicates.
