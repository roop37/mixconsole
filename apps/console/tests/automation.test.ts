import { describe, expect, it } from "vitest";
import {
  sampleCurve,
  segmentValue,
  unitToValue,
  valueAt,
  valueToUnit,
} from "../src/lib/automation";
import { PARAM_RANGES } from "../src/lib/mixscript";

describe("automation maths", () => {
  it("maps values to the unit square and back, linear and log", () => {
    const eq = PARAM_RANGES.eq_low;
    expect(valueToUnit(eq.min, eq)).toBe(0);
    expect(valueToUnit(eq.max, eq)).toBe(1);
    expect(unitToValue(valueToUnit(-6, eq), eq)).toBeCloseTo(-6);
    const hpf = PARAM_RANGES.hpf;
    expect(unitToValue(valueToUnit(1000, hpf), hpf)).toBeCloseTo(1000, 3);
    expect(unitToValue(2, hpf)).toBeCloseTo(hpf.max);
    expect(unitToValue(-1, hpf)).toBeCloseTo(hpf.min);
  });

  it("interpolates each curve type", () => {
    const a = { beat: 0, value: 0 };
    const b = { beat: 4, value: 1 };
    expect(segmentValue({ ...a, curve: "linear" }, b, 1)).toBeCloseTo(0.25);
    expect(segmentValue({ ...a, curve: "step" }, b, 3.9)).toBe(0);
    expect(segmentValue({ ...a, curve: "equal_power" }, b, 2)).toBeCloseTo(Math.SQRT1_2);
    expect(
      segmentValue({ beat: 0, value: 1, curve: "exponential" }, { beat: 4, value: 4 }, 2),
    ).toBeCloseTo(2);
    expect(segmentValue({ beat: 0, value: 0, curve: "exponential" }, b, 2)).toBe(0);
  });

  it("evaluates and samples a polyline across the transition", () => {
    const points = [
      { beat: 0, value: 1, curve: "linear" as const },
      { beat: 8, value: 0, curve: "linear" as const },
    ];
    expect(valueAt(points, -1)).toBe(1);
    expect(valueAt(points, 4)).toBe(0.5);
    expect(valueAt(points, 20)).toBe(0);
    expect(valueAt([], 3)).toBe(0);
    const sampled = sampleCurve(points, 8, 4);
    expect(sampled).toHaveLength(5);
    expect(sampled[0]).toEqual([0, 1]);
    expect(sampled[4]).toEqual([8, 0]);
  });
});
