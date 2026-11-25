import type { Job, JobEvent, MixScriptDocument } from "@mixconsole/schema-ts";
import { describe, expect, it } from "vitest";
import { type AppState, currentDoc, initialState, reducer, renderFor } from "../src/state";
import { makeDoc } from "./fixtures";

const job = (patch: Partial<Job> = {}): Job => ({
  created_at: 0,
  error: null,
  finished_at: null,
  fraction: 0,
  id: "j1",
  kind: "analyze",
  message: "",
  params: {},
  project_id: "p",
  result: null,
  stage: "queued",
  started_at: null,
  state: "queued",
  ...patch,
});
const event = (fraction: number, stage = "analyze"): JobEvent => ({
  fraction,
  message: "m",
  seq: 1,
  stage,
  ts: 0,
});
const stored = (id: string): MixScriptDocument => ({
  created_at: 0,
  document: makeDoc() as unknown as Record<string, unknown>,
  id,
  label: "x",
  parent_id: null,
  seq: 1,
  track_a: "a",
  track_b: "b",
});
const run = (state: AppState, ...actions: Parameters<typeof reducer>[1][]) =>
  actions.reduce(reducer, state);

describe("reducer", () => {
  it("tracks job progress monotonically and the final state", () => {
    let s = run(initialState(), { type: "job-start", job: job(), label: "Analysis" });
    s = run(
      s,
      { type: "job-progress", event: event(0.4) },
      { type: "job-progress", event: event(0.2) },
    );
    expect(s.job?.fraction).toBe(0.4);
    expect(s.job?.state).toBe("running");
    s = run(s, { type: "job-end", job: job({ state: "done", stage: "complete" }) });
    expect(s.job).toMatchObject({ state: "done", fraction: 1 });
    s = run(s, { type: "job-clear", id: "j1" });
    expect(s.job).toBeNull();
  });

  it("surfaces a failed job's error and ignores events for other jobs", () => {
    let s = run(initialState(), { type: "job-start", job: job(), label: "Plan" });
    s = run(s, { type: "job-end", job: job({ id: "other", state: "done" }) });
    expect(s.job?.state).toBe("queued");
    s = run(s, {
      type: "job-end",
      job: job({ state: "failed", error: "no valid transition candidates" }),
    });
    expect(s.job).toMatchObject({ state: "failed", message: "no valid transition candidates" });
    expect(run(s, { type: "job-clear", id: "j1" }).job).toBeNull();
  });

  it("commits versions, undoes and redoes, and a draft shadows the saved document", () => {
    let s = run(
      initialState(),
      { type: "version-loaded", doc: stored("v1") },
      { type: "version-loaded", doc: stored("v2") },
      { type: "commit", id: "v1" },
      { type: "commit", id: "v2" },
    );
    expect(s.history.current).toBe("v2");
    const draft = makeDoc();
    const first = draft.transitions[0];
    if (first) first.exit.seconds = 5;
    s = run(s, { type: "draft", doc: draft });
    expect(currentDoc(s)?.transitions[0]?.exit.seconds).toBe(5);
    s = run(s, { type: "undo" });
    expect(s.draft).toBeNull();
    expect(s.history.current).toBe("v1");
    expect(currentDoc(s)?.transitions[0]?.exit.seconds).toBe(32);
    s = run(s, { type: "redo" });
    expect(s.history.current).toBe("v2");
  });

  it("finds the render that belongs to the current version and format", () => {
    const rec = (id: string, mixscript_id: string, audio: string) => ({
      audio,
      created_at: 0,
      files: [audio],
      id,
      job_id: null,
      mixscript_id,
      summary: {},
    });
    let s = run(
      initialState(),
      { type: "commit", id: "v1" },
      {
        type: "renders",
        renders: [
          rec("r1", "v0", "mix.wav"),
          rec("r2", "v1", "mix.wav"),
          rec("r3", "v1", "mix.flac"),
        ],
      },
    );
    expect(renderFor(s)?.id).toBe("r3");
    expect(renderFor(s, "wav")?.id).toBe("r2");
    s = run(s, { type: "commit", id: "v2" });
    expect(renderFor(s)).toBeNull();
  });

  it("clears the plan when a deck changes and keeps options across sessions", () => {
    let s = run(
      initialState(),
      { type: "options", patch: { stems: "auto" } },
      { type: "version-loaded", doc: stored("v1") },
      { type: "commit", id: "v1" },
    );
    s = run(s, { type: "clear-plan" });
    expect(s.history.current).toBeNull();
    expect(s.versions).toEqual({});
    s = run(s, { type: "reset-session" });
    expect(s.options.stems).toBe("auto");
  });
});
