import { describe, expect, it } from "vitest";
import { fmtNum, fmtTime, NA } from "../src/lib/format";
import { checkFor, parseReport, statusOf } from "../src/lib/report";

describe("report parsing", () => {
  const report = parseReport({
    chosen_id: "c2",
    verification: [
      {
        candidate: "c1",
        passed: false,
        reason: "loudness dip",
        loudness_dip_lu: 2.1,
        drift_ms: null,
        clicks: 0,
      },
      {
        candidate: "c2",
        passed: true,
        reason: "ok",
        drift_ms: 1.2,
        loudness_dip_lu: 0.3,
        true_peak_dbtp: -1.4,
        clicks: 0,
      },
      { candidate: "c1_gain_adjusted", passed: true, reason: "ok", loudness_dip_lu: 0.9 },
      { nonsense: true },
    ],
  });

  it("keeps null metrics as null, never 0", () => {
    const c1 = report.checks[0];
    expect(c1?.metrics.drift_ms).toBeNull();
    expect(c1?.metrics.stem_leakage).toBeNull();
    expect(c1?.metrics.clicks).toBe(0);
    expect(report.checks).toHaveLength(3);
    expect(report.chosenId).toBe("c2");
  });

  it("prefers the repaired run and reports status", () => {
    expect(checkFor(report, "c1")?.candidate).toBe("c1_gain_adjusted");
    expect(statusOf(checkFor(report, "c1"))).toBe("passed");
    expect(statusOf(checkFor(report, "c2"))).toBe("passed");
    expect(statusOf(checkFor(report, "c9"))).toBe("unverified");
    expect(statusOf(null)).toBe("unverified");
  });

  it("survives garbage", () => {
    expect(parseReport(null)).toEqual({ chosenId: null, checks: [] });
    expect(parseReport({ verification: "x" }).checks).toEqual([]);
    expect(
      parseReport({ verification: [{ candidate: "a", passed: "yes", drift_ms: Number.NaN }] })
        .checks[0],
    ).toMatchObject({ passed: null });
  });
});

describe("formatting", () => {
  it("shows n/a for unmeasured values", () => {
    expect(fmtNum(null)).toBe(NA);
    expect(fmtNum(undefined, 1, "ms")).toBe(NA);
    expect(fmtNum(Number.NaN)).toBe(NA);
    expect(fmtNum(0, 1, "ms")).toBe("0.0 ms");
    expect(fmtTime(null)).toBe(NA);
    expect(fmtTime(75.34)).toBe("1:15.3");
    expect(fmtTime(5)).toBe("0:05.0");
  });
});
