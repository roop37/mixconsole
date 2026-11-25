import type { Lanes } from "@mixconsole/schema-ts";

export type SnapMode = "off" | "beat" | "downbeat" | "phrase";
export const SNAP_MODES: SnapMode[] = ["phrase", "downbeat", "beat", "off"];

export type GridLanes = Pick<Lanes, "beats" | "downbeats" | "phrases" | "duration" | "bpm">;

/** Nearest value in an ascending list (binary search); null when the list is empty. */
export function nearest(sorted: readonly number[], target: number): number | null {
  if (sorted.length === 0) return null;
  let low = 0;
  let high = sorted.length - 1;
  while (low < high) {
    const mid = (low + high) >> 1;
    if ((sorted[mid] as number) < target) low = mid + 1;
    else high = mid;
  }
  const upper = sorted[low] as number;
  const lower = low > 0 ? (sorted[low - 1] as number) : upper;
  return Math.abs(target - lower) <= Math.abs(upper - target) ? lower : upper;
}

export function gridFor(lanes: GridLanes, mode: SnapMode): number[] {
  if (mode === "phrase") {
    const phrases = lanes.phrases.map((p) => p.start);
    if (phrases.length > 0) return phrases;
    return lanes.downbeats;
  }
  if (mode === "downbeat") return lanes.downbeats.length > 0 ? lanes.downbeats : lanes.beats;
  if (mode === "beat") return lanes.beats;
  return [];
}

/** Snap a time to the chosen grid, clamped to the track. Falls back to finer grids when empty. */
export function snapTime(seconds: number, lanes: GridLanes, mode: SnapMode): number {
  const clamped = Math.min(Math.max(0, seconds), lanes.duration);
  if (mode === "off") return clamped;
  const order: SnapMode[] = ["phrase", "downbeat", "beat"];
  for (const candidate of order.slice(order.indexOf(mode))) {
    const found = nearest(gridFor(lanes, candidate), clamped);
    if (found !== null) return found;
  }
  return clamped;
}

/** Step to the next/previous grid point (keyboard nudge). Direction is +1 or -1. */
export function stepTime(
  seconds: number,
  lanes: GridLanes,
  mode: SnapMode,
  direction: 1 | -1,
): number {
  const grid = gridFor(lanes, mode === "off" ? "beat" : mode);
  const epsilon = 1e-6;
  if (direction > 0) return grid.find((t) => t > seconds + epsilon) ?? seconds;
  for (let i = grid.length - 1; i >= 0; i--) {
    if ((grid[i] as number) < seconds - epsilon) return grid[i] as number;
  }
  return seconds;
}

/** Quarter-note beat position of a cue, using the planner's convention (seconds x bpm / 60). */
export function beatOf(seconds: number, lanes: GridLanes): number {
  return (seconds * (lanes.bpm ?? 120)) / 60;
}

/** Whether a time sits on a grid point (within tolerance seconds). */
export function onGrid(
  seconds: number,
  lanes: GridLanes,
  mode: SnapMode,
  tolerance = 0.005,
): boolean {
  const found = nearest(gridFor(lanes, mode), seconds);
  return found !== null && Math.abs(found - seconds) <= tolerance;
}

export type GridLevel = "phrase" | "bar" | "beat";

/** The coarsest grid a time sits on, or null when it is off every grid. */
export function gridLevel(seconds: number, lanes: GridLanes, tolerance = 0.005): GridLevel | null {
  if (onGrid(seconds, lanes, "phrase", tolerance) && lanes.phrases.length > 0) return "phrase";
  if (onGrid(seconds, lanes, "downbeat", tolerance) && lanes.downbeats.length > 0) return "bar";
  if (onGrid(seconds, lanes, "beat", tolerance) && lanes.beats.length > 0) return "beat";
  return null;
}

export function gridText(level: GridLevel | null): string {
  return level ? `on ${level}` : "off grid";
}
