import { useQuery } from "@tanstack/react-query";
import { Cell, Legend, Pie, PieChart, Tooltip } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Chart } from "@/components/ui/chart";
import { UsageHeatmap, type HeatCell } from "@/components/usage-heatmap";
import { ApiError, api } from "@/lib/api-client";
import { CHART_COLORS } from "@/lib/time-range";

interface UsageItem {
  group_key: string;
  display_name: string | null;
  total_tokens: number;
  total_cost_usd: number;
  call_count: number;
}
interface UsageResponse {
  items: UsageItem[];
}
interface HeatmapResponse {
  timezone: string;
  cells: HeatCell[];
}

/**
 * Phase 14 (US2): provider-share donut + 24×7 usage heatmap for the usage page.
 * The heatmap grid is the shared <UsageHeatmap> (plain CSS, cheap divs).
 */
export function UsageCharts({ fromIso, toIso }: { fromIso: string; toIso: string }) {
  const byProvider = useQuery<UsageResponse, ApiError>({
    queryKey: ["admin", "viz", "provider", { fromIso, toIso }],
    queryFn: () =>
      api<UsageResponse>(
        `/admin/usage?group_by=provider&from=${encodeURIComponent(fromIso)}&to=${encodeURIComponent(toIso)}`,
      ),
  });
  const heatmap = useQuery<HeatmapResponse, ApiError>({
    queryKey: ["admin", "viz", "heatmap", { fromIso, toIso }],
    queryFn: () =>
      api<HeatmapResponse>(
        `/admin/usage/heatmap?from=${encodeURIComponent(fromIso)}&to=${encodeURIComponent(toIso)}`,
      ),
  });

  const providerData = [...(byProvider.data?.items ?? [])]
    .sort((a, b) => b.total_cost_usd - a.total_cost_usd)
    .map((p) => ({ name: p.group_key, value: p.total_cost_usd }));
  const providerTotal = providerData.reduce((s, d) => s + d.value, 0);

  const cells = heatmap.data?.cells ?? [];

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">各供應商花費占比</CardTitle>
          <CardDescription>依供應商加總（區間內計費用量）</CardDescription>
        </CardHeader>
        <CardContent>
          <Chart isLoading={byProvider.isLoading} isEmpty={providerTotal === 0} height={240} emptyText="此區間沒有計費用量">
            <PieChart>
              <Pie
                data={providerData}
                dataKey="value"
                nameKey="name"
                innerRadius={48}
                outerRadius={80}
                paddingAngle={1}
              >
                {providerData.map((d, i) => (
                  <Cell key={d.name} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
            </PieChart>
          </Chart>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">用量熱度圖</CardTitle>
          <CardDescription>星期 × 小時（時區 {heatmap.data?.timezone ?? "UTC+8"}），顏色越深用量越高</CardDescription>
        </CardHeader>
        <CardContent>
          <UsageHeatmap cells={cells} isLoading={heatmap.isLoading} />
        </CardContent>
      </Card>
    </div>
  );
}
