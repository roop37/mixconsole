import type { LibraryTrack } from "@mixconsole/schema-ts";
import { describe, expect, it } from "vitest";
import { camelotRank, sortTracks } from "../src/lib/libsort";

function track(
  name: string,
  bpm: number | null,
  camelot: string,
  energy: number | null,
): LibraryTrack {
  return {
    analyzed_at: 0,
    backend_versions: {},
    bpm,
    camelot,
    duration: 100,
    energy_mean: energy,
    energy_peak: energy,
    hash: name,
    key: "",
    lufs: null,
    path: `/m/${name}.wav`,
    paths: [],
    pcm_sha256: "",
  };
}

const rows = [
  track("b", 124, "8A", 0.5),
  track("a", null, "", null),
  track("c", 100, "12B", 0.9),
  track("d", 110, "1A", 0.1),
];

describe("library sorting", () => {
  it("sorts by bpm with unmeasured last in both directions", () => {
    expect(sortTracks(rows, "bpm", "asc").map((t) => t.hash)).toEqual(["c", "d", "b", "a"]);
    expect(sortTracks(rows, "bpm", "desc").map((t) => t.hash)).toEqual(["b", "d", "c", "a"]);
  });
  it("sorts by key on the Camelot wheel", () => {
    expect(camelotRank("8A")).toBe(8);
    expect(camelotRank("8B")).toBe(8.5);
    expect(camelotRank("")).toBeNull();
    expect(camelotRank("13A")).toBe(13);
    expect(sortTracks(rows, "key", "asc").map((t) => t.hash)).toEqual(["d", "b", "c", "a"]);
  });
  it("sorts by energy and name without mutating the input", () => {
    const before = rows.map((t) => t.hash);
    expect(sortTracks(rows, "energy", "desc").map((t) => t.hash)).toEqual(["c", "b", "d", "a"]);
    expect(sortTracks(rows, "name", "asc").map((t) => t.hash)).toEqual(["a", "b", "c", "d"]);
    expect(rows.map((t) => t.hash)).toEqual(before);
  });
});
