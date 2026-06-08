import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
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
import { fmtCompact } from "@/lib/number-format";
import { CHART_COLORS, rangeToIso, type TimeRange } from "@/lib/time-range";

interface TimeseriesPoint {
  ts: string;
  tokens: number;
  cost_usd: number;
  call_count: number;
}
interface MyTimeseriesResponse {
  points: TimeseriesPoint[];
}
interface BreakdownItem {
  group_key: string;
  display_name: string | null;
  total_tokens: number;
  total_cost_usd: number;
  call_count: number;
}
interface MyUsageResponse {
  breakdown?: BreakdownItem[];
}

const fmtInt = new Intl.NumberFormat("zh-TW");
const fmtUsd = (n: number) => `$${n.toFixed(n < 1 ? 4 : 2)}`;

/**
 * Phase 17: charts of the MEMBER's OWN usage (daily trend + spend-by-model),
 * for the member dashboard. Both queries are member-scoped server-side (scope
 * from session) — this component never sees cross-member data. Reuses the shared
 * <Chart>/CHART_COLORS and the same RWD rules (base grid-cols-1) as the admin
 * charts. Query keys live under ["me","viz",...] so they never collide with the
 * admin ["admin","viz",...] cache.
 */
export function MemberUsageCharts({ range }: { range: TimeRange }) {
  const { fromIso, toIso } = rangeToIso(range);
  const [metric, setMetric] = useState<"cost" | "tokens">("cost");
  const qs = `from=${encodeURIComponent(fromIso)}&to=${encodeURIComponent(toIso)}`;

  const ts = useQuery<MyTimeseriesResponse, ApiError>({
    queryKey: ["me", "viz", "timeseries", { fromIso, toIso }],
    queryFn: () => api<MyTimeseriesResponse>(`/me/usage/timeseries?${qs}`),
  });
  const byModel = useQuery<MyUsageResponse, ApiError>({
    queryKey: ["me", "viz", "model", { fromIso, toIso }],
    queryFn: () => api<MyUsageResponse>(`/me/usage?group_by=model&${qs}`),
  });

  const dailyData = (ts.data?.points ?? []).map((p) => ({
    day: p.ts.slice(5, 10),
    value: metric === "cost" ? p.cost_usd : p.tokens,
    tokens: p.tokens,
    cost_usd: p.cost_usd,
    call_count: p.call_count,
  }));

  const modelItems = [...(byModel.data?.breakdown ?? [])].sort(
    (a, b) => b.total_cost_usd - a.total_cost_usd,
  );
  const topModels = modelItems.slice(0, 5);
  const restModels = modelItems.slice(5);
  const donutData = [
    ...topModels.map((m) => ({ name: m.display_name ?? m.group_key, value: m.total_cost_usd })),
    ...(restModels.length
      ? [{ name: "其他", value: restModels.reduce((s, m) => s + m.total_cost_usd, 0) }]
      : []),
  ];
  const donutTotal = donutData.reduce((s, d) => s + d.value, 0);

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle className="text-base">我的每日用量</CardTitle>
            <CardDescription>跨我所有憑證加總（只看自己）</CardDescription>
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
              <Bar dataKey="value" fill={CHART_COLORS[0]} radius={[3, 3, 0, 0]} />
            </BarChart>
          </Chart>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">我的各 Model 花費</CardTitle>
          <CardDescription>我的花費集中在哪些模型</CardDescription>
        </CardHeader>
        <CardContent>
          <Chart
            isLoading={byModel.isLoading}
            isEmpty={donutTotal === 0}
            height={240}
            emptyText="此區間沒有計費用量"
          >
            <PieChart>
              <Pie
                data={donutData}
                dataKey="value"
                nameKey="name"
                innerRadius={48}
                outerRadius={80}
                paddingAngle={1}
              >
                {donutData.map((d, i) => (
                  <Cell key={d.name} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => fmtUsd(v)} />
            </PieChart>
          </Chart>
        </CardContent>
      </Card>
    </div>
  );
}
