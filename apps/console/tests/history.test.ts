import { describe, expect, it } from "vitest";
import { canRedo, canUndo, commit, emptyHistory, redo, undo } from "../src/lib/history";

describe("version history", () => {
  it("undo and redo walk the versions", () => {
    let h = commit(commit(commit(emptyHistory, "v1"), "v2"), "v3");
    expect(h).toEqual({ current: "v3", past: ["v1", "v2"], future: [] });
    h = undo(undo(h));
    expect(h.current).toBe("v1");
    expect(canUndo(h)).toBe(false);
    expect(canRedo(h)).toBe(true);
    h = redo(h);
    expect(h).toEqual({ current: "v2", past: ["v1"], future: ["v3"] });
  });

  it("a new edit after undo discards redo but never forgets the past", () => {
    let h = commit(commit(emptyHistory, "v1"), "v2");
    h = undo(h);
    h = commit(h, "v3");
    expect(h).toEqual({ current: "v3", past: ["v1"], future: [] });
  });

  it("is a no-op at the ends and for the same version", () => {
    expect(undo(emptyHistory)).toBe(emptyHistory);
    expect(redo(emptyHistory)).toBe(emptyHistory);
    const h = commit(emptyHistory, "v1");
    expect(commit(h, "v1")).toBe(h);
    expect(undo(h)).toBe(h);
  });
});
