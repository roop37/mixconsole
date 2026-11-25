import type { Span2 } from "@mixconsole/schema-ts";

export interface View {
  start: number;
  end: number;
}

/** Items of an ascending list inside [start, end] (binary search, so huge lanes stay cheap). */
export function pickVisible(sorted: readonly number[], view: View, margin = 0): [number, number] {
  let low = 0;
  let high = sorted.length;
  while (low < high) {
    const mid = (low + high) >> 1;
    if ((sorted[mid] as number) < view.start - margin) low = mid + 1;
    else high = mid;
  }
  const first = low;
  high = sorted.length;
  while (low < high) {
    const mid = (low + high) >> 1;
    if ((sorted[mid] as number) <= view.end + margin) low = mid + 1;
    else high = mid;
  }
  return [first, low];
}

export function timeToX(seconds: number, view: View, width: number): number {
  return ((seconds - view.start) / (view.end - view.start)) * width;
}

export function xToTime(x: number, view: View, width: number): number {
  return view.start + (x / width) * (view.end - view.start);
}

/** Normalised 0..1 bar energy (peak = 1); empty or flat data maps to all zeros, not NaN. */
export function normaliseEnergy(values: readonly number[]): number[] {
  const peak = values.reduce((m, v) => (Number.isFinite(v) && v > m ? v : m), 0);
  return values.map((v) => (peak > 0 && Number.isFinite(v) ? Math.max(0, v) / peak : 0));
}

export function spansOverlapping(spans: readonly Span2[], view: View): Span2[] {
  return spans.filter((s) => s.end >= view.start && s.start <= view.end);
}

const SECTION_HUES: Record<string, number> = {
  intro: 205,
  verse: 160,
  chorus: 20,
  drop: 340,
  build: 45,
  break: 270,
  breakdown: 270,
  outro: 215,
  bridge: 120,
};

export function sectionHue(label: string | null): number {
  if (!label) return 220;
  const known = SECTION_HUES[label.toLowerCase()];
  if (known !== undefined) return known;
  let h = 0;
  for (const c of label) h = (h * 31 + c.charCodeAt(0)) % 360;
  return h;
}
