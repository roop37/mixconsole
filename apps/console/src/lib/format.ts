/** Display helpers. A missing measurement is "n/a" (not measured), never 0. */

export const NA = "n/a";

export function fmtNum(value: number | null | undefined, digits = 2, unit = ""): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return NA;
  return `${value.toFixed(digits)}${unit ? ` ${unit}` : ""}`;
}

export function fmtTime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return NA;
  const sign = seconds < 0 ? "-" : "";
  const total = Math.abs(seconds);
  const minutes = Math.floor(total / 60);
  const rest = total - minutes * 60;
  return `${sign}${minutes}:${rest.toFixed(1).padStart(4, "0")}`;
}

export function fmtScore(value: number | null | undefined): string {
  return fmtNum(value, 3);
}

const FAMILY_LABELS: Record<string, string> = {
  gapless: "Gapless",
  trim_crossfade: "Trim crossfade",
  cut_on_downbeat: "Cut on downbeat",
  beatmatch_blend: "Beatmatch blend",
  stem_handoff: "Stem handoff",
  filter_sweep: "Filter sweep",
  echo_out: "Echo out",
  vocal_over_instrumental: "Vocal over instrumental",
};

export function familyLabel(family: string): string {
  return FAMILY_LABELS[family] ?? family;
}

export const FAMILIES = Object.keys(FAMILY_LABELS);

export function titleCase(name: string): string {
  const spaced = name.replaceAll("_", " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function basename(path: string): string {
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] ?? path;
}
