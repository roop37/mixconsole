# 0003: Service facade and jobs

Status: Accepted; facade implemented, HTTP jobs delivered in M4.5 (see 0008).

## Context

Terminal coupling would force the server and desktop clients to rewrite orchestration.

## Decision

Route clients through a pure Python service with progress callbacks, cooperative cancellation and bounded processes. Return results in input order.

## Consequences

Native DSP calls finish before cancellation checkpoints. Persistent job IDs, queue state and SSE arrived in M4.5 ([0008](0008-sqlite-jobs-api.md)).
