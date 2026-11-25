import type { AutomationLane, AutomationPoint, MixScript, Transition } from "@mixconsole/schema-ts";
import { beatOf, type GridLanes, snapTime } from "./snap";

export type CueKind = "exit" | "entry";
export type LockField = "family" | "exit" | "entry" | "length_bars";

/** The API stores MixScript documents as opaque JSON; this is the single typed boundary. */
export function asMixScript(document: Record<string, unknown>): MixScript {
  const candidate = document as Partial<MixScript>;
  if (!candidate.transitions?.length || !candidate.tracks) {
    throw new Error("not a MixScript with a transition");
  }
  return document as unknown as MixScript;
}

export function transitionOf(doc: MixScript): Transition {
  const first = doc.transitions[0];
  if (!first) throw new Error("MixScript has no transition");
  return first;
}

export function clone<T>(value: T): T {
  return structuredClone(value);
}

function edit(doc: MixScript, change: (transition: Transition) => void): MixScript {
  const next = clone(doc);
  change(transitionOf(next));
  return next;
}

function withLock(transition: Transition, name: string, locked = true): void {
  const locks = new Set(transition.locks ?? []);
  if (locked) locks.add(name);
  else locks.delete(name);
  transition.locks = [...locks].sort();
}

export function isLocked(transition: Transition, name: string): boolean {
  return (transition.locks ?? []).includes(name);
}

export function toggleLock(doc: MixScript, name: string): MixScript {
  return edit(doc, (t) => withLock(t, name, !isLocked(t, name)));
}

/** Seconds of one reference bar for the transition (tempo map first point, else the cue tempo). */
export function barSeconds(transition: Transition): number {
  const bpm = transition.tempo.tempo_map?.[0]?.bpm;
  return bpm ? (60 / bpm) * (transition.beats_per_bar ?? 4) : 2;
}

export function transitionSeconds(transition: Transition): number {
  return transition.length_bars * barSeconds(transition);
}

/**
 * Move a cue. The seconds are snapped by the caller; the beat uses the planner convention.
 * The per-beat warp map belongs to the old cue, so it is dropped (the renderer then uses the
 * constant tempo map) and the cue is locked so a re-plan keeps it.
 */
export function moveCue(
  doc: MixScript,
  which: CueKind,
  seconds: number,
  lanes: GridLanes,
  mode: Parameters<typeof snapTime>[2],
): MixScript {
  const snapped = snapTime(seconds, lanes, mode);
  return edit(doc, (t) => {
    t[which] = { ...t[which], seconds: snapped, beat: beatOf(snapped, lanes) };
    if (t.extensions && "render.beat_warp" in t.extensions) {
      const { "render.beat_warp": _dropped, ...rest } = t.extensions;
      t.extensions = rest;
    }
    withLock(t, which);
  });
}

/** The planner's lock dict for a re-plan: only locked fields, with their current values. */
export function planLocks(doc: MixScript): Record<string, unknown> | null {
  const t = transitionOf(doc);
  const locks: Record<string, unknown> = {};
  if (isLocked(t, "family")) locks.family = t.family;
  if (isLocked(t, "exit")) locks.exit = t.exit.seconds;
  if (isLocked(t, "entry")) locks.entry = t.entry.seconds;
  if (isLocked(t, "length_bars")) locks.length_bars = t.length_bars;
  return Object.keys(locks).length > 0 ? locks : null;
}

export function laneLabel(lane: AutomationLane): string {
  const target =
    lane.target.kind === "stem" ? `${lane.target.track} ${lane.target.stem}` : lane.target.track;
  return `${target.replace("deck_", "Deck ").toUpperCase()} ${lane.parameter.replace("_", " ")}`;
}

export interface ParamRange {
  min: number;
  max: number;
  unit: string;
  log: boolean;
}

export const PARAM_RANGES: Record<AutomationLane["parameter"], ParamRange> = {
  gain: { min: 0, max: 1.5, unit: "x", log: false },
  eq_low: { min: -30, max: 12, unit: "dB", log: false },
  eq_mid: { min: -30, max: 12, unit: "dB", log: false },
  eq_high: { min: -30, max: 12, unit: "dB", log: false },
  hpf: { min: 20, max: 20000, unit: "Hz", log: true },
  lpf: { min: 200, max: 21000, unit: "Hz", log: true },
  delay_send: { min: 0, max: 1, unit: "x", log: false },
};

export function clampValue(parameter: AutomationLane["parameter"], value: number): number {
  const range = PARAM_RANGES[parameter];
  return Math.min(range.max, Math.max(range.min, value));
}

const MIN_GAP = 0.01;

function lanePoints(transition: Transition, laneId: string): AutomationPoint[] {
  const lane = transition.automation?.find((l) => l.id === laneId);
  if (!lane) throw new Error(`no automation lane ${laneId}`);
  return lane.points;
}

/** Move a point; its beat stays strictly between its neighbours and within the transition. */
export function movePoint(
  doc: MixScript,
  laneId: string,
  index: number,
  beat: number,
  value: number,
): MixScript {
  return edit(doc, (t) => {
    const lane = t.automation?.find((l) => l.id === laneId);
    if (!lane) return;
    const points = lanePoints(t, laneId);
    const previous = points[index - 1];
    const following = points[index + 1];
    const total = t.length_bars * (t.beats_per_bar ?? 4);
    const low = previous ? previous.beat + MIN_GAP : 0;
    const high = following ? following.beat - MIN_GAP : Math.max(total, low);
    const point = points[index];
    if (!point) return;
    point.beat = Math.round(Math.min(high, Math.max(low, beat)) * 1000) / 1000;
    point.value = Math.round(clampValue(lane.parameter, value) * 10000) / 10000;
    withLock(t, laneId);
  });
}

export function addPoint(doc: MixScript, laneId: string, beat: number, value: number): MixScript {
  return edit(doc, (t) => {
    const lane = t.automation?.find((l) => l.id === laneId);
    if (!lane) return;
    const rounded = Math.round(beat * 1000) / 1000;
    if (lane.points.some((p) => Math.abs(p.beat - rounded) < MIN_GAP)) return;
    lane.points.push({ beat: rounded, value: clampValue(lane.parameter, value), curve: "linear" });
    lane.points.sort((a, b) => a.beat - b.beat);
    withLock(t, laneId);
  });
}

export function removePoint(doc: MixScript, laneId: string, index: number): MixScript {
  return edit(doc, (t) => {
    const lane = t.automation?.find((l) => l.id === laneId);
    if (!lane || lane.points.length <= 1) return;
    lane.points.splice(index, 1);
    withLock(t, laneId);
  });
}

export function setCurve(
  doc: MixScript,
  laneId: string,
  index: number,
  curve: NonNullable<AutomationPoint["curve"]>,
): MixScript {
  return edit(doc, (t) => {
    const point = t.automation?.find((l) => l.id === laneId)?.points[index];
    if (!point) return;
    point.curve = curve;
    withLock(t, laneId);
  });
}

/** Validation the UI can do before a round trip (the server stays authoritative). */
export function validateAutomation(lane: AutomationLane): string | null {
  for (let i = 1; i < lane.points.length; i++) {
    if ((lane.points[i] as AutomationPoint).beat <= (lane.points[i - 1] as AutomationPoint).beat) {
      return "automation beats must be strictly increasing";
    }
  }
  for (let i = 0; i < lane.points.length - 1; i++) {
    const a = lane.points[i] as AutomationPoint;
    const b = lane.points[i + 1] as AutomationPoint;
    if (a.curve === "exponential" && (a.value <= 0 || b.value <= 0)) {
      return "exponential segments need positive endpoints";
    }
  }
  return null;
}
