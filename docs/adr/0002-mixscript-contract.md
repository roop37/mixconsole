# 0002: MixScript as the editing contract

Status: Accepted; v1.1 implemented.

## Context

CLI, planners and future editors need a shared portable representation.

## Decision

Use versioned Pydantic models and generated JSON Schema; migrate v1 deterministically. Stable IDs, locks, candidates and extensions preserve user edits.

## Consequences

Semantic validation remains in Python; JSON Schema supplies structural checks. Rendering and planner enforcement follow in M2.
