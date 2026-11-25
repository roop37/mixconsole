import type { Lanes, MixScript } from "@mixconsole/schema-ts";

/** 120 BPM grid: beats every 0.5 s, bars every 2 s, phrases every 8 bars (16 s). */
export function makeLanes(duration = 64): Lanes {
  const beats = Array.from({ length: Math.floor(duration / 0.5) }, (_, i) => i * 0.5);
  const downbeats = beats.filter((_, i) => i % 4 === 0);
  return {
    bar_energy: downbeats.map((_, i) => (i % 8) / 7),
    bars: downbeats.map((start) => ({ start, end: start + 2 })),
    beats,
    bpm: 120,
    downbeats,
    duration,
    meter: 4,
    phrases: [0, 16, 32, 48].map((start, i) => ({
      confidence: 0.8,
      length_bars: 8,
      start,
      start_bar: i * 8,
    })),
    sections: [],
    vocal_source: null,
    vocals: [],
  };
}

export function makeDoc(): MixScript {
  return {
    version: "mixscript/v1.1",
    tracks: {
      deck_a: { content_sha256: "a".repeat(64), duration: 64, sample_rate: 44100 },
      deck_b: { content_sha256: "b".repeat(64), duration: 64, sample_rate: 44100 },
    },
    transitions: [
      {
        id: "transition_1",
        from_track: "deck_a",
        to_track: "deck_b",
        family: "beatmatch_blend",
        exit: { beat: 64, seconds: 32 },
        entry: { beat: 0, seconds: 0 },
        length_bars: 4,
        beats_per_bar: 4,
        extensions: { "render.beat_warp": [[0, 0]] },
        tempo: {
          strategy: "none",
          reference_track: "deck_a",
          tempo_map: [{ beat: 0, bpm: 120 }],
        },
        key: { strategy: "none", semitones: 0 },
        automation: [
          {
            id: "gain_a",
            target: { kind: "track", track: "deck_a" },
            parameter: "gain",
            points: [
              { beat: 0, value: 1, curve: "linear" },
              { beat: 8, value: 0.5, curve: "linear" },
              { beat: 16, value: 0, curve: "equal_power" },
            ],
          },
        ],
        effects: [],
        candidates: [],
        locks: [],
      },
    ],
    provenance: { analysis_backends: {}, scorer_version: "t", seed: 0 },
  };
}
