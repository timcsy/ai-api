import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Chart } from "@/components/ui/chart";
import { TimeRangeSelect } from "@/components/time-range-select";
import { UsageHeatmap, type HeatCell } from "@/components/usage-heatmap";
import { ApiError, api } from "@/lib/api-client";
import { fmtCompact } from "@/lib/number-format";
import { CHART_COLORS, presetRange, rangeToIso } from "@/lib/time-range";

interface TimeseriesPoint {
  ts: string;
  tokens: number;
  cost_usd: number;
  call_count: number;
}
interface TimeseriesResponse {
  points: TimeseriesPoint[];
}
interface HeatmapResponse {
  timezone: string;
  cells: HeatCell[];
}

const fmtInt = new Intl.NumberFormat("zh-TW");
const fmtUsd = (n: number) => `$${n.toFixed(n < 1 ? 4 : 2)}`;

/**
 * Per-allocation usage charts (Phase 18 follow-up): a daily time-series line +
 * weekday×hour heatmap for ONE allocation. Both endpoints are owner-checked
 * server-side (`/me/allocations/{id}/usage/*`); this component never sees another
 * member's data. Reuses the shared <Chart>/<UsageHeatmap>/<TimeRangeSelect>.
 */
export function AllocationUsageCharts({ allocationId }: { allocationId: string }) {
  const [range, setRange] = useState(() => presetRange("month"));
  const [metric, setMetric] = useState<"cost" | "tokens">("tokens");
  const { fromIso, toIso } = rangeToIso(range);
  const qs = `from=${encodeURIComponent(fromIso)}&to=${encodeURIComponent(toIso)}`;
  const base = `/me/allocations/${allocationId}/usage`;

  const ts = useQuery<TimeseriesResponse, ApiError>({
    queryKey: ["me", "alloc-viz", "timeseries", allocationId, { fromIso, toIso }],
    queryFn: () => api<TimeseriesResponse>(`${base}/timeseries?${qs}`),
    enabled: !!allocationId,
  });
  const heatmap = useQuery<HeatmapResponse, ApiError>({
    queryKey: ["me", "alloc-viz", "heatmap", allocationId, { fromIso, toIso }],
    queryFn: () => api<HeatmapResponse>(`${base}/heatmap?${qs}`),
    enabled: !!allocationId,
  });

  const dailyData = (ts.data?.points ?? []).map((p) => ({
    day: p.ts.slice(5, 10),
    value: metric === "cost" ? p.cost_usd : p.tokens,
    tokens: p.tokens,
    cost_usd: p.cost_usd,
    call_count: p.call_count,
  }));
  const cells = heatmap.data?.cells ?? [];

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="text-lg">這筆分配的用量</CardTitle>
            <CardDescription>每日趨勢與時段熱度（只看這個分配）</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <div className="inline-flex rounded-md border text-xs">
              <button
                type="button"
                onClick={() => setMetric("tokens")}
                className={`px-2 py-1 rounded-l-md ${metric === "tokens" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
              >
                Token
              </button>
              <button
                type="button"
                onClick={() => setMetric("cost")}
                className={`px-2 py-1 rounded-r-md ${metric === "cost" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
              >
                花費
              </button>
            </div>
            <TimeRangeSelect value={range} onChange={setRange} />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <div>
          <div className="mb-2 text-sm font-medium text-muted-foreground">每日趨勢</div>
          <Chart isLoading={ts.isLoading} isEmpty={dailyData.length === 0} height={220}>
            <LineChart data={dailyData} margin={{ top: 8, right: 8, bottom: 4, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="day" fontSize={11} tickLine={false} />
              <YAxis
                fontSize={11}
                tickLine={false}
                width={40}
                tickFormatter={(v: number) => (metric === "cost" ? fmtUsd(v) : fmtCompact(v))}
              />
              <Tooltip
                formatter={(_v, _n, item) => {
                  const p = item.payload as (typeof dailyData)[number];
                  return [
                    `${fmtInt.format(p.tokens)} tokens · ${fmtUsd(p.cost_usd)} · ${p.call_count} 次`,
                    p.day,
                  ];
                }}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke={CHART_COLORS[0]}
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </Chart>
        </div>
        <div>
          <div className="mb-2 text-sm font-medium text-muted-foreground">
            時段熱度（星期 x 小時，時區 {heatmap.data?.timezone ?? "UTC+8"}）
          </div>
          <UsageHeatmap cells={cells} isLoading={heatmap.isLoading} />
        </div>
      </CardContent>
    </Card>
  );
}
