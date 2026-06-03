export type RangePreset = "week" | "month" | "quarter" | "custom";

export interface TimeRange {
  preset: RangePreset;
  from: string; // YYYY-MM-DD
  to: string; // YYYY-MM-DD
}

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Compute {from,to} (YYYY-MM-DD) for a preset, relative to today. */
export function presetRange(preset: RangePreset, prev?: TimeRange): TimeRange {
  const today = new Date();
  const to = isoDate(today);
  if (preset === "week") {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    return { preset, from: isoDate(d), to };
  }
  if (preset === "month") {
    const d = new Date();
    d.setMonth(d.getMonth() - 1);
    return { preset, from: isoDate(d), to };
  }
  if (preset === "quarter") {
    const d = new Date();
    d.setMonth(d.getMonth() - 3);
    return { preset, from: isoDate(d), to };
  }
  return {
    preset: "custom",
    from: prev?.from ?? presetRange("month").from,
    to: prev?.to ?? to,
  };
}

/** Convert a TimeRange (YYYY-MM-DD) to ISO datetime bounds (UTC day edges). */
export function rangeToIso(r: TimeRange): { fromIso: string; toIso: string } {
  return { fromIso: `${r.from}T00:00:00Z`, toIso: `${r.to}T23:59:59Z` };
}

/** Shared categorical palette for donut/pie slices (provider / model). */
export const CHART_COLORS = [
  "hsl(221 83% 53%)", // blue
  "hsl(142 71% 45%)", // green
  "hsl(35 92% 52%)", // amber
  "hsl(280 65% 60%)", // purple
  "hsl(0 72% 58%)", // red
  "hsl(200 18% 60%)", // muted grey (Other)
];
