# Concepts

| Term | Meaning in MixConsole |
| --- | --- |
| Beat | A quarter-note position in a track's estimated pulse grid. |
| Downbeat | The first beat of a bar. |
| Bar | A group of beats; the current analyzer estimates 3/4 or 4/4. |
| Phrase | A musical unit spanning 4, 8 or 16 bars; the last unit may be truncated. |
| Section | An estimated interval separated by timbral or energy changes; semantic labels are not inferred yet. |
| Cue | A possible entry or exit location; future planners choose among proposals. |
| Tempo map | Local BPM estimates over time, allowing a changing pulse. |
| PCM hash | Identity of canonical decoded float32 stereo audio at 44.1 kHz. |
| File hash | Identity of the original file bytes. |
| MixScript | An editable data contract for transition intent, not a recording. |

Analysis timestamps are seconds. MixScript automation is measured in reference-track
quarter notes relative to the transition start. Cues retain source seconds/beats.
The [reference](mixscript.md) describes these fields. Analysis is estimated, and
unusual meter, rubato or percussion-free music can challenge the core backends.
