# 0003: Service facade and jobs

Status: Accepted; facade implemented, HTTP jobs planned for M4.5.

## Context

Terminal coupling would force the server and desktop clients to rewrite orchestration.

## Decision

Route clients through a pure Python service with progress callbacks, cooperative cancellation and bounded processes. Return results in input order.

## Consequences

Native DSP calls finish before cancellation checkpoints. Persistent job IDs, queue state and SSE arrive in M4.5.
