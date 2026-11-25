import { describe, expect, it } from "vitest";
import {
  beatOf,
  gridFor,
  gridLevel,
  gridText,
  nearest,
  onGrid,
  snapTime,
  stepTime,
} from "../src/lib/snap";
import { makeLanes } from "./fixtures";

const lanes = makeLanes();

describe("snap", () => {
  it("finds the nearest value, ties go to the earlier one", () => {
    expect(nearest([0, 2, 4], 2.9)).toBe(2);
    expect(nearest([0, 2, 4], 3)).toBe(2);
    expect(nearest([0, 2, 4], 3.1)).toBe(4);
    expect(nearest([], 1)).toBeNull();
    expect(nearest([5], -10)).toBe(5);
  });

  it("snaps to phrases, downbeats and beats", () => {
    expect(snapTime(21, lanes, "phrase")).toBe(16);
    expect(snapTime(25, lanes, "phrase")).toBe(32);
    expect(snapTime(21.3, lanes, "downbeat")).toBe(22);
    expect(snapTime(21.3, lanes, "beat")).toBe(21.5);
    expect(snapTime(21.3, lanes, "off")).toBe(21.3);
  });

  it("clamps to the track and falls back to finer grids", () => {
    expect(snapTime(-5, lanes, "off")).toBe(0);
    expect(snapTime(999, lanes, "off")).toBe(64);
    const noPhrases = { ...lanes, phrases: [] };
    expect(gridFor(noPhrases, "phrase")).toEqual(lanes.downbeats);
    expect(snapTime(21.3, noPhrases, "phrase")).toBe(22);
    const onlyBeats = { ...lanes, phrases: [], downbeats: [] };
    expect(snapTime(21.3, onlyBeats, "phrase")).toBe(21.5);
    const nothing = { ...lanes, phrases: [], downbeats: [], beats: [] };
    expect(snapTime(21.3, nothing, "phrase")).toBe(21.3);
  });

  it("steps along the grid and stops at the ends", () => {
    expect(stepTime(16, lanes, "phrase", 1)).toBe(32);
    expect(stepTime(16, lanes, "phrase", -1)).toBe(0);
    expect(stepTime(0, lanes, "phrase", -1)).toBe(0);
    expect(stepTime(48, lanes, "phrase", 1)).toBe(48);
    expect(stepTime(10, lanes, "off", 1)).toBe(10.5);
  });

  it("uses the planner's beat convention", () => {
    expect(beatOf(32, lanes)).toBe(64);
    expect(beatOf(10, { ...lanes, bpm: null })).toBe(20);
  });

  it("reports whether a time is on the grid", () => {
    expect(onGrid(16, lanes, "phrase")).toBe(true);
    expect(onGrid(16.5, lanes, "phrase")).toBe(false);
    expect(onGrid(16.5, lanes, "beat")).toBe(true);
  });

  it("names the coarsest grid a cue sits on", () => {
    expect(gridLevel(16, lanes)).toBe("phrase");
    expect(gridLevel(18, lanes)).toBe("bar");
    expect(gridLevel(18.5, lanes)).toBe("beat");
    expect(gridLevel(18.25, lanes)).toBeNull();
    expect(gridText(null)).toBe("off grid");
    expect(gridText("bar")).toBe("on bar");
    expect(gridLevel(18, { ...lanes, phrases: [], downbeats: [], beats: [] })).toBeNull();
  });
});
