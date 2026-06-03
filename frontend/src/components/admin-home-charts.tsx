import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Chart } from "@/components/ui/chart";
import { ApiError, api } from "@/lib/api-client";
import { CHART_COLORS, rangeToIso, type TimeRange } from "@/lib/time-range";

interface TimeseriesPoint {
  ts: string;
  tokens: number;
  cost_usd: number;
  call_count: number;
}
interface TimeseriesResponse {
  points: TimeseriesPoint[];
}
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

function qs(fromIso: string, toIso: string): string {
  return `from=${encodeURIComponent(fromIso)}&to=${encodeURIComponent(toIso)}`;
}

const fmtInt = new Intl.NumberFormat("zh-TW");
const fmtUsd = (n: number) => `$${n.toFixed(n < 1 ? 4 : 2)}`;

/**
 * Phase 14 (US1): the three admin-home charts. Kept in its own component file
 * so the home route stays readable and so recharts is imported only here. Range
 * is lifted to the parent (US3 swaps in <TimeRangeSelect>); every chart shares
 * the same {from,to} so they move together.
 */
export function DashboardCharts({ range }: { range: TimeRange }) {
  const { fromIso, toIso } = rangeToIso(range);
  const navigate = useNavigate();
  const [metric, setMetric] = useState<"cost" | "tokens">("cost");

  const ts = useQuery<TimeseriesResponse, ApiError>({
    queryKey: ["admin", "viz", "timeseries", { fromIso, toIso }],
    queryFn: () =>
      api<TimeseriesResponse>(`/admin/usage/timeseries?bucket=day&${qs(fromIso, toIso)}`),
  });
  const byModel = useQuery<UsageResponse, ApiError>({
    queryKey: ["admin", "viz", "model", { fromIso, toIso }],
    queryFn: () => api<UsageResponse>(`/admin/usage?group_by=model&${qs(fromIso, toIso)}`),
  });
  const byAlloc = useQuery<UsageResponse, ApiError>({
    queryKey: ["admin", "viz", "allocation", { fromIso, toIso }],
    queryFn: () => api<UsageResponse>(`/admin/usage?group_by=allocation&${qs(fromIso, toIso)}`),
  });

  // --- Daily spend bar ---
  const dailyData = (ts.data?.points ?? []).map((p) => ({
    day: p.ts.slice(5, 10), // MM-DD
    value: metric === "cost" ? p.cost_usd : p.tokens,
    tokens: p.tokens,
    cost_usd: p.cost_usd,
    call_count: p.call_count,
  }));

  // --- Spend by model donut (top 5 + 其他) ---
  const modelItems = [...(byModel.data?.items ?? [])].sort(
    (a, b) => b.total_cost_usd - a.total_cost_usd,
  );
  const topModels = modelItems.slice(0, 5);
  const restModels = modelItems.slice(5);
  const donutData = [
    ...topModels.map((m) => ({
      name: m.display_name ?? m.group_key,
      slug: m.group_key,
      value: m.total_cost_usd,
    })),
    ...(restModels.length
      ? [
          {
            name: "其他",
            slug: null as string | null,
            value: restModels.reduce((s, m) => s + m.total_cost_usd, 0),
          },
        ]
      : []),
  ];
  const donutTotal = donutData.reduce((s, d) => s + d.value, 0);

  // --- Top 5 allocations bar ---
  const allocData = [...(byAlloc.data?.items ?? [])]
    .sort((a, b) => b.total_cost_usd - a.total_cost_usd)
    .slice(0, 5)
    .map((a) => ({
      name: a.display_name ?? a.group_key,
      cost_usd: a.total_cost_usd,
      tokens: a.total_tokens,
    }));

  // --- Top 5 tags by spend (US5) — a card, not a chart ---
  const byTag = useQuery<UsageResponse, ApiError>({
    queryKey: ["admin", "viz", "tag", { fromIso, toIso }],
    queryFn: () => api<UsageResponse>(`/admin/usage?group_by=tag&${qs(fromIso, toIso)}`),
  });
  const topTags = [...(byTag.data?.items ?? [])]
    .sort((a, b) => b.total_cost_usd - a.total_cost_usd)
    .slice(0, 5);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle className="text-base">每日用量</CardTitle>
            <CardDescription>所有分配加總（{range.from} ~ {range.to}）</CardDescription>
          </div>
          <div className="inline-flex rounded-md border text-xs">
            <button
              type="button"
              onClick={() => setMetric("cost")}
              className={`px-2 py-1 rounded-l-md ${metric === "cost" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
            >
              花費
            </button>
            <button
              type="button"
              onClick={() => setMetric("tokens")}
              className={`px-2 py-1 rounded-r-md ${metric === "tokens" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
            >
              Token
            </button>
          </div>
        </CardHeader>
        <CardContent>
          <Chart isLoading={ts.isLoading} isEmpty={dailyData.length === 0} height={220}>
            <BarChart data={dailyData} margin={{ top: 8, right: 8, bottom: 4, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="day" fontSize={11} tickLine={false} />
              <YAxis
                fontSize={11}
                tickLine={false}
                width={48}
                tickFormatter={(v: number) =>
                  metric === "cost" ? fmtUsd(v) : fmtInt.format(v)
                }
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
              <Bar dataKey="value" fill={CHART_COLORS[0]} radius={[3, 3, 0, 0]} />
            </BarChart>
          </Chart>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">各 Model 花費占比</CardTitle>
            <CardDescription>前 5 名 + 其他，點扇形看 model 詳情</CardDescription>
          </CardHeader>
          <CardContent>
            <Chart isLoading={byModel.isLoading} isEmpty={donutTotal === 0} height={240} emptyText="此區間沒有計費用量">
              <PieChart>
                <Pie
                  data={donutData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={48}
                  outerRadius={80}
                  paddingAngle={1}
                  onClick={(d) => {
                    const slug = (d as unknown as { slug: string | null }).slug;
                    if (slug) navigate(`/admin/model/${slug}`);
                  }}
                >
                  {donutData.map((d, i) => (
                    <Cell
                      key={d.name}
                      fill={CHART_COLORS[i % CHART_COLORS.length]}
                      cursor={d.slug ? "pointer" : "default"}
                    />
                  ))}
                </Pie>
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Tooltip formatter={(v: number) => fmtUsd(v)} />
              </PieChart>
            </Chart>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top 5 分配（依花費）</CardTitle>
            <CardDescription>點長條前往分配維運頁</CardDescription>
          </CardHeader>
          <CardContent>
            <Chart isLoading={byAlloc.isLoading} isEmpty={allocData.length === 0} height={240}>
              <BarChart
                data={allocData}
                layout="vertical"
                margin={{ top: 4, right: 12, bottom: 4, left: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis
                  type="number"
                  fontSize={11}
                  tickLine={false}
                  tickFormatter={(v: number) => fmtUsd(v)}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  fontSize={11}
                  tickLine={false}
                  width={120}
                />
                <Tooltip
                  formatter={(_v, _n, item) => {
                    const p = item.payload as (typeof allocData)[number];
                    return [`${fmtUsd(p.cost_usd)} · ${fmtInt.format(p.tokens)} tokens`, p.name];
                  }}
                />
                <Bar
                  dataKey="cost_usd"
                  fill={CHART_COLORS[1]}
                  radius={[0, 3, 3, 0]}
                  cursor="pointer"
                  onClick={() => navigate("/admin/observability/allocations")}
                />
              </BarChart>
            </Chart>
          </CardContent>
        </Card>
      </div>

      {/* US5: Top 5 tags by spend — a plain card placed AFTER the charts so the
          ≤3-charts-per-page constraint still holds. */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Top 5 群組／班級（依花費）</CardTitle>
          <CardDescription>依 Tag 加總；成員可掛多 tag，數字可能重複計算</CardDescription>
        </CardHeader>
        <CardContent>
          {byTag.isLoading ? (
            <p className="text-sm text-muted-foreground">載入中…</p>
          ) : topTags.length === 0 ? (
            <p className="text-sm text-muted-foreground">此區間沒有掛 tag 的用量</p>
          ) : (
            <ul className="divide-y text-sm">
              {topTags.map((t) => (
                <li key={t.group_key}>
                  <button
                    type="button"
                    onClick={() => navigate("/admin/usage?group_by=tag")}
                    className="flex w-full items-center justify-between py-2 hover:bg-muted/50"
                  >
                    <span className="font-medium">{t.group_key}</span>
                    <span className="text-muted-foreground">
                      {fmtUsd(t.total_cost_usd)} · {fmtInt.format(t.total_tokens)} tokens
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
