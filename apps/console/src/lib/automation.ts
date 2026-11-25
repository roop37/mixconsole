import type { AutomationPoint } from "@mixconsole/schema-ts";
import type { ParamRange } from "./mixscript";

/** Value (in the parameter's unit) to a 0..1 vertical position (1 = top). */
export function valueToUnit(value: number, range: ParamRange): number {
  if (range.log) {
    const span = Math.log(range.max) - Math.log(range.min);
    return (Math.log(Math.max(value, range.min)) - Math.log(range.min)) / span;
  }
  return (value - range.min) / (range.max - range.min);
}

export function unitToValue(unit: number, range: ParamRange): number {
  const u = Math.min(1, Math.max(0, unit));
  if (range.log) {
    return Math.exp(Math.log(range.min) + u * (Math.log(range.max) - Math.log(range.min)));
  }
  return range.min + u * (range.max - range.min);
}

/** Interpolate between two points with the curve of the first (it "leads to" the next). */
export function segmentValue(a: AutomationPoint, b: AutomationPoint, beat: number): number {
  const span = b.beat - a.beat;
  const t = span <= 0 ? 1 : Math.min(1, Math.max(0, (beat - a.beat) / span));
  switch (a.curve ?? "linear") {
    case "step":
      return a.value;
    case "equal_power":
      return a.value + (b.value - a.value) * Math.sin((t * Math.PI) / 2);
    case "exponential":
      return a.value > 0 && b.value > 0 ? a.value * (b.value / a.value) ** t : a.value;
    default:
      return a.value + (b.value - a.value) * t;
  }
}

export function valueAt(points: readonly AutomationPoint[], beat: number): number {
  const first = points[0];
  if (!first) return 0;
  if (beat <= first.beat) return first.value;
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i] as AutomationPoint;
    const b = points[i + 1] as AutomationPoint;
    if (beat <= b.beat) return segmentValue(a, b, beat);
  }
  return (points[points.length - 1] as AutomationPoint).value;
}

/** Sampled polyline for drawing: [beat, value] pairs across [0, totalBeats]. */
export function sampleCurve(
  points: readonly AutomationPoint[],
  totalBeats: number,
  steps = 96,
): [number, number][] {
  const out: [number, number][] = [];
  for (let i = 0; i <= steps; i++) {
    const beat = (totalBeats * i) / steps;
    out.push([beat, valueAt(points, beat)]);
  }
  return out;
}

export function formatParam(value: number, range: ParamRange): string {
  if (range.unit === "Hz")
    return value >= 1000 ? `${(value / 1000).toFixed(1)} kHz` : `${Math.round(value)} Hz`;
  if (range.unit === "dB") return `${value.toFixed(1)} dB`;
  return value.toFixed(2);
}
