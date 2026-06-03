import { useQuery } from "@tanstack/react-query";
import { Cell, Legend, Pie, PieChart, Tooltip } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Chart } from "@/components/ui/chart";
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
interface HeatCell {
  weekday: number; // 0=Sunday
  hour: number;
  tokens: number;
  call_count: number;
}
interface HeatmapResponse {
  timezone: string;
  cells: HeatCell[];
}

const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];
const fmtInt = new Intl.NumberFormat("zh-TW");

/**
 * Phase 14 (US2): provider-share donut + 24×7 usage heatmap for the usage page.
 * The heatmap is a plain CSS grid (not recharts) — 168 coloured cells render far
 * cheaper as divs, per research §heatmap.
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
  const cellMap = new Map(cells.map((c) => [`${c.weekday}-${c.hour}`, c]));
  const maxTokens = cells.reduce((m, c) => Math.max(m, c.tokens), 0);

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">各 Provider 花費占比</CardTitle>
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
          {heatmap.isLoading ? (
            <div className="h-[200px] animate-pulse rounded-md bg-muted/50" />
          ) : cells.length === 0 ? (
            <div className="flex h-[200px] items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
              此區間沒有資料
            </div>
          ) : (
            <div className="overflow-x-auto">
              <div className="inline-grid gap-[2px]" style={{ gridTemplateColumns: "auto repeat(24, 12px)" }}>
                {/* header row: hour labels (0,3,6,...) */}
                <div />
                {Array.from({ length: 24 }, (_, h) => (
                  <div key={`h-${h}`} className="text-[8px] text-muted-foreground text-center">
                    {h % 3 === 0 ? h : ""}
                  </div>
                ))}
                {WEEKDAYS.map((label, wd) => (
                  <Row key={wd} label={label} wd={wd} cellMap={cellMap} maxTokens={maxTokens} />
                ))}
              </div>
              <p className="mt-2 text-[10px] text-muted-foreground">列＝星期（日～六），欄＝0–23 時</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Row({
  label,
  wd,
  cellMap,
  maxTokens,
}: {
  label: string;
  wd: number;
  cellMap: Map<string, HeatCell>;
  maxTokens: number;
}) {
  return (
    <>
      <div className="pr-1 text-[10px] text-muted-foreground leading-[12px]">週{label}</div>
      {Array.from({ length: 24 }, (_, h) => {
        const c = cellMap.get(`${wd}-${h}`);
        const intensity = c && maxTokens > 0 ? 0.12 + 0.88 * (c.tokens / maxTokens) : 0;
        return (
          <div
            key={h}
            className="h-[12px] w-[12px] rounded-[2px] border border-border/30"
            style={{ backgroundColor: c ? `rgba(37, 99, 235, ${intensity})` : "transparent" }}
            title={
              c
                ? `週${label} ${h}:00 — ${fmtInt.format(c.tokens)} tokens · ${c.call_count} 次`
                : `週${label} ${h}:00 — 無`
            }
          />
        );
      })}
    </>
  );
}
