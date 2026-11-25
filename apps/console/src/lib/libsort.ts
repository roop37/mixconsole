import type { LibraryTrack } from "@mixconsole/schema-ts";
import { basename } from "./format";

export type SortKey = "name" | "bpm" | "key" | "energy" | "duration" | "lufs";
export type SortDir = "asc" | "desc";

/** Camelot "8A" -> sortable number (8 + 0 for A, 0.5 for B); unknown -> null. */
export function camelotRank(camelot: string | null | undefined): number | null {
  const match = /^(\d{1,2})([AB])$/i.exec((camelot ?? "").trim());
  if (!match) return null;
  return Number(match[1]) + (match[2]?.toUpperCase() === "B" ? 0.5 : 0);
}

function sortValue(track: LibraryTrack, key: SortKey): number | string | null {
  switch (key) {
    case "name":
      return basename(track.path).toLowerCase();
    case "bpm":
      return track.bpm;
    case "key":
      return camelotRank(track.camelot);
    case "energy":
      return track.energy_mean;
    case "duration":
      return track.duration;
    case "lufs":
      return track.lufs;
  }
}

/** Sort with unmeasured values always last, whatever the direction. */
export function sortTracks(
  tracks: readonly LibraryTrack[],
  key: SortKey,
  dir: SortDir,
): LibraryTrack[] {
  const sign = dir === "asc" ? 1 : -1;
  return [...tracks].sort((a, b) => {
    const x = sortValue(a, key);
    const y = sortValue(b, key);
    if (x === null && y === null) return 0;
    if (x === null) return 1;
    if (y === null) return -1;
    if (typeof x === "string" || typeof y === "string")
      return sign * String(x).localeCompare(String(y));
    return sign * (x - y);
  });
}
