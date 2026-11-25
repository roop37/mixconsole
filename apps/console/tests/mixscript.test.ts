import { describe, expect, it } from "vitest";
import {
  addPoint,
  asMixScript,
  barSeconds,
  clampValue,
  isLocked,
  moveCue,
  movePoint,
  planLocks,
  removePoint,
  setCurve,
  toggleLock,
  transitionOf,
  transitionSeconds,
  validateAutomation,
} from "../src/lib/mixscript";
import { makeDoc, makeLanes } from "./fixtures";

const lanes = makeLanes();

describe("cue edits", () => {
  it("snaps, sets beat+seconds, locks the cue and drops the stale warp map", () => {
    const doc = makeDoc();
    const next = moveCue(doc, "exit", 21, lanes, "phrase");
    const t = transitionOf(next);
    expect(t.exit).toEqual({ seconds: 16, beat: 32 });
    expect(t.locks).toEqual(["exit"]);
    expect(t.extensions?.["render.beat_warp"]).toBeUndefined();
    // the input is never mutated
    expect(transitionOf(doc).exit.seconds).toBe(32);
    expect(transitionOf(doc).extensions?.["render.beat_warp"]).toBeDefined();
  });

  it("moves the entry cue independently", () => {
    const next = moveCue(makeDoc(), "entry", 33.2, lanes, "downbeat");
    expect(transitionOf(next).entry.seconds).toBe(34);
    expect(transitionOf(next).exit.seconds).toBe(32);
  });
});

describe("locks", () => {
  it("toggles and exposes planner locks with their values", () => {
    let doc = toggleLock(makeDoc(), "family");
    doc = toggleLock(doc, "exit");
    doc = toggleLock(doc, "gain_a");
    expect(isLocked(transitionOf(doc), "gain_a")).toBe(true);
    expect(planLocks(doc)).toEqual({ family: "beatmatch_blend", exit: 32 });
    doc = toggleLock(doc, "family");
    expect(planLocks(doc)).toEqual({ exit: 32 });
    expect(planLocks(makeDoc())).toBeNull();
  });
});

describe("automation edits", () => {
  it("keeps beats strictly increasing and values in range", () => {
    const doc = makeDoc();
    const moved = movePoint(doc, "gain_a", 1, 99, 9);
    const points = transitionOf(moved).automation?.[0]?.points ?? [];
    expect(points[1]?.beat).toBeLessThan(points[2]?.beat ?? 0);
    expect(points[1]?.value).toBe(1.5);
    expect(validateAutomation(transitionOf(moved).automation?.[0] ?? (null as never))).toBeNull();
    const first = movePoint(doc, "gain_a", 0, -3, 0.2);
    expect(transitionOf(first).automation?.[0]?.points[0]?.beat).toBe(0);
    expect(isLocked(transitionOf(first), "gain_a")).toBe(true);
  });

  it("adds, sorts, de-duplicates and removes points", () => {
    const doc = makeDoc();
    const added = addPoint(doc, "gain_a", 4, 0.8);
    expect(transitionOf(added).automation?.[0]?.points.map((p) => p.beat)).toEqual([0, 4, 8, 16]);
    const same = addPoint(added, "gain_a", 4.001, 0.1);
    expect(transitionOf(same).automation?.[0]?.points).toHaveLength(4);
    const removed = removePoint(added, "gain_a", 1);
    expect(transitionOf(removed).automation?.[0]?.points).toHaveLength(3);
    let single = doc;
    for (let i = 0; i < 5; i++) single = removePoint(single, "gain_a", 0);
    expect(transitionOf(single).automation?.[0]?.points).toHaveLength(1);
  });

  it("changes curves and validates exponential segments", () => {
    const next = setCurve(makeDoc(), "gain_a", 0, "exponential");
    expect(transitionOf(next).automation?.[0]?.points[0]?.curve).toBe("exponential");
    const lane = structuredClone(transitionOf(next).automation?.[0]);
    if (!lane) throw new Error("lane");
    lane.points[1] = { beat: 8, value: 0, curve: "linear" };
    expect(validateAutomation(lane)).toMatch(/exponential/);
    lane.points[1] = { beat: 0, value: 1 };
    expect(validateAutomation(lane)).toMatch(/increasing/);
  });

  it("clamps parameter values", () => {
    expect(clampValue("hpf", 5)).toBe(20);
    expect(clampValue("eq_low", -99)).toBe(-30);
    expect(clampValue("delay_send", 2)).toBe(1);
  });
});

describe("helpers", () => {
  it("computes bar and transition lengths from the tempo map", () => {
    const t = transitionOf(makeDoc());
    expect(barSeconds(t)).toBe(2);
    expect(transitionSeconds(t)).toBe(8);
  });

  it("rejects documents that are not a MixScript with a transition", () => {
    expect(() => asMixScript({})).toThrow();
    expect(() => asMixScript({ tracks: {}, transitions: [] })).toThrow();
    expect(asMixScript(makeDoc() as unknown as Record<string, unknown>).version).toBe(
      "mixscript/v1.1",
    );
  });
});
