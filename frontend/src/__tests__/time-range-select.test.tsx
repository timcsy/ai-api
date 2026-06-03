import { describe, expect, it } from "vitest";

import { presetRange, rangeToIso } from "@/lib/time-range";

function daysBetween(from: string, to: string): number {
  return Math.round(
    (new Date(`${to}T00:00:00Z`).getTime() - new Date(`${from}T00:00:00Z`).getTime()) / 86_400_000,
  );
}

describe("presetRange (Phase 14 US3)", () => {
  it("本週 spans 7 days", () => {
    const r = presetRange("week");
    expect(r.preset).toBe("week");
    expect(daysBetween(r.from, r.to)).toBe(7);
  });

  it("本月 spans about a month (28–31 days)", () => {
    const r = presetRange("month");
    expect(r.preset).toBe("month");
    expect(daysBetween(r.from, r.to)).toBeGreaterThanOrEqual(28);
    expect(daysBetween(r.from, r.to)).toBeLessThanOrEqual(31);
  });

  it("本季 spans about three months (88–92 days)", () => {
    const r = presetRange("quarter");
    expect(r.preset).toBe("quarter");
    expect(daysBetween(r.from, r.to)).toBeGreaterThanOrEqual(88);
    expect(daysBetween(r.from, r.to)).toBeLessThanOrEqual(92);
  });

  it("自訂 keeps the previous range's dates", () => {
    const prev = { preset: "custom" as const, from: "2026-01-01", to: "2026-02-01" };
    const r = presetRange("custom", prev);
    expect(r.from).toBe("2026-01-01");
    expect(r.to).toBe("2026-02-01");
  });

  it("rangeToIso produces UTC day-edge bounds", () => {
    const { fromIso, toIso } = rangeToIso({ preset: "custom", from: "2026-05-01", to: "2026-05-31" });
    expect(fromIso).toBe("2026-05-01T00:00:00Z");
    expect(toIso).toBe("2026-05-31T23:59:59Z");
  });
});
