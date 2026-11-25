/** Parse a render's report.json (a file artifact, not an API schema) defensively. */

export interface Check {
  candidate: string;
  passed: boolean | null;
  reason: string;
  metrics: Record<string, number | null>;
}

export interface Report {
  chosenId: string | null;
  checks: Check[];
}

const METRIC_KEYS = [
  "drift_ms",
  "loudness_dip_lu",
  "loudness_bump_lu",
  "true_peak_dbtp",
  "clicks",
  "low_overlap_bars",
  "vocal_overlap_seconds",
  "bass_overlap_bars",
  "stem_leakage",
] as const;

export const METRIC_LABELS: Record<(typeof METRIC_KEYS)[number], { label: string; unit: string }> =
  {
    drift_ms: { label: "Beat drift", unit: "ms" },
    loudness_dip_lu: { label: "Loudness dip", unit: "LU" },
    loudness_bump_lu: { label: "Loudness bump", unit: "LU" },
    true_peak_dbtp: { label: "True peak", unit: "dBTP" },
    clicks: { label: "Clicks", unit: "" },
    low_overlap_bars: { label: "Low-end overlap", unit: "bars" },
    vocal_overlap_seconds: { label: "Vocal overlap", unit: "s" },
    bass_overlap_bars: { label: "Bass overlap", unit: "bars" },
    stem_leakage: { label: "Stem leakage", unit: "" },
  };

export const metricKeys = METRIC_KEYS;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseReport(raw: unknown): Report {
  if (!isRecord(raw)) return { chosenId: null, checks: [] };
  const verification = Array.isArray(raw.verification) ? raw.verification : [];
  const checks: Check[] = [];
  for (const item of verification) {
    if (!isRecord(item) || typeof item.candidate !== "string") continue;
    const metrics: Record<string, number | null> = {};
    for (const key of METRIC_KEYS) {
      const value = item[key];
      metrics[key] = typeof value === "number" && Number.isFinite(value) ? value : null;
    }
    checks.push({
      candidate: item.candidate,
      passed: typeof item.passed === "boolean" ? item.passed : null,
      reason: typeof item.reason === "string" ? item.reason : "",
      metrics,
    });
  }
  return { chosenId: typeof raw.chosen_id === "string" ? raw.chosen_id : null, checks };
}

export type VerifyStatus = "passed" | "failed" | "unverified";

/** Best check for a candidate: its repaired (gain adjusted) run wins over the first one. */
export function checkFor(report: Report | null, candidateId: string): Check | null {
  if (!report) return null;
  const matches = report.checks.filter(
    (c) => c.candidate === candidateId || c.candidate.startsWith(`${candidateId}_`),
  );
  return matches[matches.length - 1] ?? null;
}

export function statusOf(check: Check | null): VerifyStatus {
  if (!check || check.passed === null) return "unverified";
  return check.passed ? "passed" : "failed";
}
