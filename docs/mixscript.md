# MixScript v1.1 reference

Generated from the JSON Schema; do not edit.

Schema validation checks structure. Python validation also enforces references,
unique IDs, ordered points, cue/play bounds and locks. M2 renders the six
stem-free families; M3 renders `stem_handoff` and `vocal_over_instrumental`
(per-stem gain lanes) when stems are available.

## MixScript

Versioned, shareable transition specification, independent of audio paths.

| Field | Required | Schema |
| --- | --- | --- |
| explanation | no | `{"anyOf": [{"$ref": "#/$defs/Explanation"}, {"type": "null"}], "default": null}` |
| extensions | no | `{"additionalProperties": true, "title": "Extensions", "type": "object"}` |
| provenance | yes | `{"$ref": "#/$defs/Provenance"}` |
| tracks | yes | `{"minProperties": 1, "patternProperties": {"^[A-Za-z0-9_-]+$": {"$ref": "#/$defs/Track"}}, "title": "Tracks", "type": "object"}` |
| transitions | yes | `{"items": {"$ref": "#/$defs/Transition"}, "title": "Transitions", "type": "array"}` |
| version | yes | `{"const": "mixscript/v1.1", "type": "string"}` |

## AutomationLane

Gain/send use linear amplitude, EQ uses dB, and HPF/LPF use Hz.

| Field | Required | Schema |
| --- | --- | --- |
| extensions | no | `{"additionalProperties": true, "title": "Extensions", "type": "object"}` |
| id | yes | `{"pattern": "^[A-Za-z0-9_-]+$", "type": "string"}` |
| parameter | yes | `{"enum": ["gain", "eq_low", "eq_mid", "eq_high", "hpf", "lpf", "delay_send"], "title": "Parameter", "type": "string"}` |
| points | yes | `{"items": {"$ref": "#/$defs/AutomationPoint"}, "minItems": 1, "title": "Points", "type": "array"}` |
| target | yes | `{"discriminator": {"mapping": {"stem": "#/$defs/StemTarget", "track": "#/$defs/TrackTarget"}, "propertyName": "kind"}, "oneOf": [{"$ref": "#/$defs/TrackTarget"}, {"$ref": "#/$defs/StemTarget"}], "title": "Target"}` |

## AutomationPoint

Beat is relative to transition start on the reference grid; curve leads to next point.

| Field | Required | Schema |
| --- | --- | --- |
| beat | yes | `{"minimum": 0, "title": "Beat", "type": "number"}` |
| curve | no | `{"default": "linear", "enum": ["step", "linear", "equal_power", "exponential"], "title": "Curve", "type": "string"}` |
| extensions | no | `{"additionalProperties": true, "title": "Extensions", "type": "object"}` |
| value | yes | `{"title": "Value", "type": "number"}` |

## CandidateSummary

Inspectable alternative; preview is an artifact reference, not audio bytes.

| Field | Required | Schema |
| --- | --- | --- |
| entry | yes | `{"$ref": "#/$defs/CuePoint"}` |
| exit | yes | `{"$ref": "#/$defs/CuePoint"}` |
| extensions | no | `{"additionalProperties": true, "title": "Extensions", "type": "object"}` |
| family | yes | `{"enum": ["gapless", "trim_crossfade", "cut_on_downbeat", "beatmatch_blend", "stem_handoff", "filter_sweep", "echo_out", "vocal_over_instrumental"], "title": "Family", "type": "string"}` |
| id | yes | `{"pattern": "^[A-Za-z0-9_-]+$", "title": "Id", "type": "string"}` |
| length_bars | yes | `{"minimum": 0, "title": "Length Bars", "type": "integer"}` |
| preview_artifact | no | `{"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Preview Artifact"}` |
| score | yes | `{"title": "Score", "type": "number"}` |
| score_breakdown | no | `{"additionalProperties": {"type": "number"}, "title": "Score Breakdown", "type": "object"}` |

## CuePoint

Zero-based source position; beats are quarter notes on that track's grid.

| Field | Required | Schema |
| --- | --- | --- |
| beat | yes | `{"minimum": 0, "title": "Beat", "type": "number"}` |
| extensions | no | `{"additionalProperties": true, "title": "Extensions", "type": "object"}` |
| seconds | yes | `{"minimum": 0, "title": "Seconds", "type": "number"}` |

## Effect

Named effect with scalar parameters; rendering support arrives after M0.

| Field | Required | Schema |
| --- | --- | --- |
| extensions | no | `{"additionalProperties": true, "title": "Extensions", "type": "object"}` |
| id | yes | `{"pattern": "^[A-Za-z0-9_-]+$", "type": "string"}` |
| name | yes | `{"minLength": 1, "title": "Name", "type": "string"}` |
| params | no | `{"additionalProperties": {"anyOf": [{"type": "number"}, {"type": "string"}, {"type": "boolean"}]}, "title": "Params", "type": "object"}` |
| target | yes | `{"discriminator": {"mapping": {"stem": "#/$defs/StemTarget", "track": "#/$defs/TrackTarget"}, "propertyName": "kind"}, "oneOf": [{"$ref": "#/$defs/TrackTarget"}, {"$ref": "#/$defs/StemTarget"}], "title": "Target"}` |

## Explanation

Human-readable planning rationale.

| Field | Required | Schema |
| --- | --- | --- |
| chosen_because | yes | `{"minLength": 1, "title": "Chosen Because", "type": "string"}` |
| extensions | no | `{"additionalProperties": true, "title": "Extensions", "type": "object"}` |
| rejected_candidates | no | `{"items": {"$ref": "#/$defs/RejectedCandidate"}, "title": "Rejected Candidates", "type": "array"}` |
| score_breakdown | no | `{"additionalProperties": {"type": "number"}, "title": "Score Breakdown", "type": "object"}` |

## KeyStrategy

Pitch intent; permission and stem feasibility are checked by later planners.

| Field | Required | Schema |
| --- | --- | --- |
| extensions | no | `{"additionalProperties": true, "title": "Extensions", "type": "object"}` |
| semitones | no | `{"default": 0, "enum": [-1, 0, 1], "title": "Semitones", "type": "integer"}` |
| strategy | yes | `{"enum": ["none", "pitch_shift"], "title": "Strategy", "type": "string"}` |

## PlayRegion

Half-open source region in seconds; omitted means the complete track.

| Field | Required | Schema |
| --- | --- | --- |
| extensions | no | `{"additionalProperties": true, "title": "Extensions", "type": "object"}` |
| in_seconds | yes | `{"minimum": 0, "title": "In Seconds", "type": "number"}` |
| out_seconds | yes | `{"exclusiveMinimum": 0, "title": "Out Seconds", "type": "number"}` |

## Provenance

Versions and random seed needed to reproduce planning decisions.

| Field | Required | Schema |
| --- | --- | --- |
| analysis_backends | yes | `{"additionalProperties": {"minLength": 1, "type": "string"}, "title": "Analysis Backends", "type": "object"}` |
| extensions | no | `{"additionalProperties": true, "title": "Extensions", "type": "object"}` |
| scorer_version | yes | `{"minLength": 1, "title": "Scorer Version", "type": "string"}` |
| seed | yes | `{"minimum": 0, "title": "Seed", "type": "integer"}` |

## RejectedCandidate

A candidate ID and a human-readable reason for rejecting it.

| Field | Required | Schema |
| --- | --- | --- |
| candidate_id | yes | `{"pattern": "^[A-Za-z0-9_-]+$", "title": "Candidate Id", "type": "string"}` |
| extensions | no | `{"additionalProperties": true, "title": "Extensions", "type": "object"}` |
| family | yes | `{"enum": ["gapless", "trim_crossfade", "cut_on_downbeat", "beatmatch_blend", "stem_handoff", "filter_sweep", "echo_out", "vocal_over_instrumental"], "title": "Family", "type": "string"}` |
| reason | yes | `{"minLength": 1, "title": "Reason", "type": "string"}` |
| score | no | `{"anyOf": [{"type": "number"}, {"type": "null"}], "default": null, "title": "Score"}` |

## StemTarget

Apply automation or an effect to a separated stem.

| Field | Required | Schema |
| --- | --- | --- |
| extensions | no | `{"additionalProperties": true, "title": "Extensions", "type": "object"}` |
| kind | yes | `{"const": "stem", "title": "Kind", "type": "string"}` |
| stem | yes | `{"enum": ["drums", "bass", "other", "vocals"], "title": "Stem", "type": "string"}` |
| track | yes | `{"pattern": "^[A-Za-z0-9_-]+$", "title": "Track", "type": "string"}` |

## TempoPoint

Reference tempo at a transition-relative quarter-note beat; linear between points.

| Field | Required | Schema |
| --- | --- | --- |
| beat | yes | `{"minimum": 0, "title": "Beat", "type": "number"}` |
| bpm | yes | `{"exclusiveMinimum": 0, "title": "Bpm", "type": "number"}` |
| extensions | no | `{"additionalProperties": true, "title": "Extensions", "type": "object"}` |

## TempoStrategy

Tempo intent plus an explicit reference tempo map, when known.

| Field | Required | Schema |
| --- | --- | --- |
| extensions | no | `{"additionalProperties": true, "title": "Extensions", "type": "object"}` |
| reference_track | yes | `{"pattern": "^[A-Za-z0-9_-]+$", "title": "Reference Track", "type": "string"}` |
| strategy | yes | `{"enum": ["none", "meet_in_middle", "ramp_b_to_a_then_back", "no_sync"], "title": "Strategy", "type": "string"}` |
| tempo_map | no | `{"items": {"$ref": "#/$defs/TempoPoint"}, "title": "Tempo Map", "type": "array"}` |

## Track

A track identified by SHA-256 of canonical decoded PCM (see mixconsole.io).

| Field | Required | Schema |
| --- | --- | --- |
| content_sha256 | yes | `{"pattern": "^[0-9a-f]{64}$", "title": "Content Sha256", "type": "string"}` |
| display_name | no | `{"anyOf": [{"type": "string"}, {"type": "null"}], "default": null, "title": "Display Name"}` |
| duration | yes | `{"description": "Duration in seconds of canonical decoded audio.", "exclusiveMinimum": 0, "title": "Duration", "type": "number"}` |
| extensions | no | `{"additionalProperties": true, "title": "Extensions", "type": "object"}` |
| play | no | `{"anyOf": [{"$ref": "#/$defs/PlayRegion"}, {"type": "null"}], "default": null}` |
| sample_rate | yes | `{"exclusiveMinimum": 0, "title": "Sample Rate", "type": "integer"}` |

## TrackTarget

Apply automation or an effect to a whole track.

| Field | Required | Schema |
| --- | --- | --- |
| extensions | no | `{"additionalProperties": true, "title": "Extensions", "type": "object"}` |
| kind | yes | `{"const": "track", "title": "Kind", "type": "string"}` |
| track | yes | `{"pattern": "^[A-Za-z0-9_-]+$", "title": "Track", "type": "string"}` |

## Transition

An ordered handoff between two track IDs.

| Field | Required | Schema |
| --- | --- | --- |
| automation | no | `{"items": {"$ref": "#/$defs/AutomationLane"}, "title": "Automation", "type": "array"}` |
| beats_per_bar | no | `{"default": 4, "description": "Quarter-note beats per reference bar.", "exclusiveMinimum": 0, "title": "Beats Per Bar", "type": "integer"}` |
| candidates | no | `{"items": {"$ref": "#/$defs/CandidateSummary"}, "title": "Candidates", "type": "array"}` |
| effects | no | `{"items": {"$ref": "#/$defs/Effect"}, "title": "Effects", "type": "array"}` |
| entry | yes | `{"$ref": "#/$defs/CuePoint"}` |
| exit | yes | `{"$ref": "#/$defs/CuePoint"}` |
| explanation | no | `{"anyOf": [{"$ref": "#/$defs/Explanation"}, {"type": "null"}], "default": null}` |
| extensions | no | `{"additionalProperties": true, "title": "Extensions", "type": "object"}` |
| family | yes | `{"enum": ["gapless", "trim_crossfade", "cut_on_downbeat", "beatmatch_blend", "stem_handoff", "filter_sweep", "echo_out", "vocal_over_instrumental"], "title": "Family", "type": "string"}` |
| from_track | yes | `{"pattern": "^[A-Za-z0-9_-]+$", "title": "From Track", "type": "string"}` |
| id | yes | `{"pattern": "^[A-Za-z0-9_-]+$", "type": "string"}` |
| key | yes | `{"$ref": "#/$defs/KeyStrategy"}` |
| length_bars | yes | `{"minimum": 0, "title": "Length Bars", "type": "integer"}` |
| locks | no | `{"items": {"type": "string"}, "title": "Locks", "type": "array", "uniqueItems": true}` |
| tempo | yes | `{"$ref": "#/$defs/TempoStrategy"}` |
| to_track | yes | `{"pattern": "^[A-Za-z0-9_-]+$", "title": "To Track", "type": "string"}` |
