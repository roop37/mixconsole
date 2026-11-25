# 0001: MIT License

Status: accepted (2026-11-25). Supersedes the pre-publication Apache-2.0 choice; no code was published under Apache-2.0.

## Context
MixConsole should be easy to adopt in hobby, research and commercial tools. All core dependencies are MIT/BSD/ISC/Apache-2.0
compatible with a permissive project licence.

## Decision
Use the MIT License for project code. Dependencies and model weights retain their own terms (see THIRD_PARTY.md). GPL tools
may run only as optional external processes and are never imported, linked or vendored. Non-commercial weights are never defaults.

## Consequences
Simple, widely understood terms. No explicit patent grant (Apache-2.0 had one); accepted for simplicity.
