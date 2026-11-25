import { describe, expect, it } from "vitest";
import { normaliseEnergy, pickVisible, sectionHue, timeToX, xToTime } from "../src/lib/lanes";

describe("lane helpers", () => {
  it("picks the visible slice of a long sorted list", () => {
    const beats = Array.from({ length: 1000 }, (_, i) => i * 0.5);
    const [from, to] = pickVisible(beats, { start: 10, end: 12 });
    expect(beats.slice(from, to)).toEqual([10, 10.5, 11, 11.5, 12]);
    expect(pickVisible([], { start: 0, end: 1 })).toEqual([0, 0]);
    const [a, b] = pickVisible(beats, { start: 10, end: 12 }, 1);
    expect(beats.slice(a, b)[0]).toBe(9);
  });

  it("maps time and pixels both ways", () => {
    const view = { start: 10, end: 20 };
    expect(timeToX(15, view, 1000)).toBe(500);
    expect(xToTime(500, view, 1000)).toBe(15);
    expect(xToTime(timeToX(12.34, view, 777), view, 777)).toBeCloseTo(12.34);
  });

  it("normalises energy without NaN for flat or empty data", () => {
    expect(normaliseEnergy([1, 2, 4])).toEqual([0.25, 0.5, 1]);
    expect(normaliseEnergy([0, 0])).toEqual([0, 0]);
    expect(normaliseEnergy([])).toEqual([]);
    expect(normaliseEnergy([Number.NaN, 2])).toEqual([0, 1]);
  });

  it("gives sections stable hues", () => {
    expect(sectionHue("drop")).toBe(sectionHue("Drop"));
    expect(sectionHue("weird")).toBe(sectionHue("weird"));
    expect(sectionHue(null)).toBeGreaterThanOrEqual(0);
  });
});
