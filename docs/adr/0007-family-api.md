# 0007: Transition family plugin API

Status: Accepted for M2.

## Context

The M2 planner needs six stem-free families while later milestones add stems and
third-party transition templates. The service and MixScript contracts already
exist, so a family should supply proposals and DSP intent without a new facade.

## Decision

A family class has `name`, `version`, `candidates(a, b, ctx)`,
`applicable(a, b, candidate)` and `automation(candidate)`. Built-ins register in
`plan.families`; optional classes load from the `mixconsole.families` entry-point
group. The planner applies shared hard constraints, records every rejection,
pre-scores each family, keeps a configured top-k and caps the total at 60.
`automation` returns MixScript v1.1 lanes and effects. The renderer consumes
those fields, and provenance records the family through its name and fixed
implementation version.

## Consequences

The v1.1 schema enumerates the six M2 families plus reserved M3 names. A plugin
can replace neither a built-in name nor introduce a new family string without a
future schema revision. Broken plugins are logged and skipped. The deterministic
candidate ordering uses score and stable cue/id tie-breaks.
