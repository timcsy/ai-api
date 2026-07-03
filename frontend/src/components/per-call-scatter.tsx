import { useState } from "react";
import { CartesianGrid, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";

import { Button } from "@/components/ui/button";
import { Chart } from "@/components/ui/chart";
import { CHART_COLORS } from "@/lib/time-range";

/** One call record as consumed by the scatter (spec 056). */
export interface CallPoint {
  id: string;
  started_at: string;
  model?: string | null;
  total_tokens?: number | null;
  cost_usd?: string | number | null;
  quantity?: number | null;
  unit?: string | null;
  outcome: string;
  status_code?: number;
}

const fmtUsd = (n: number) => `$${n.toFixed(n < 1 ? 4 : 2)}`;
const fmtInt = new Intl.NumberFormat("zh-TW");

/**
 * Per-call scatter (spec 056): every dot is ONE call. x = time, y = cost or
 * tokens (toggle). Outliers (a single big call) pop out; hover shows detail.
 * Shared by the admin records page and the member's own allocation view.
 */
export function PerCallScatter({ records }: { records: CallPoint[] }) {
  const [metric, setMetric] = useState<"cost" | "tokens">("cost");

  const points = records
    .map((r) => {
      const y =
        metric === "cost"
          ? r.cost_usd == null
            ? null
            : Number(r.cost_usd)
          : (r.total_tokens ?? null);
      return y == null ? null : { x: new Date(r.started_at).getTime(), y, rec: r };
    })
    .filter((p): p is { x: number; y: number; rec: CallPoint } => p !== null);

  const ok = points.filter((p) => p.rec.outcome === "success");
  const bad = points.filter((p) => p.rec.outcome !== "success");

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          每個點是一次呼叫（{metric === "cost" ? "y=花費" : "y=tokens"}）；hover 看細節
          {metric === "cost" && "。未定價的呼叫不畫在花費軸。"}
        </p>
        <div className="flex gap-1">
          <Button size="sm" variant={metric === "cost" ? "default" : "outline"} onClick={() => setMetric("cost")}>花費</Button>
          <Button size="sm" variant={metric === "tokens" ? "default" : "outline"} onClick={() => setMetric("tokens")}>tokens</Button>
        </div>
      </div>
      {points.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">此區間沒有可畫的呼叫。</p>
      ) : (
        <Chart>
          <ScatterChart margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              type="number"
              dataKey="x"
              domain={["dataMin", "dataMax"]}
              fontSize={11}
              tickFormatter={(v) => new Date(v).toLocaleString("zh-TW", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}
            />
            <YAxis
              type="number"
              dataKey="y"
              fontSize={11}
              tickFormatter={(v) => (metric === "cost" ? fmtUsd(v) : fmtInt.format(v))}
            />
            <Tooltip content={<CallTooltip metric={metric} />} />
            <Scatter data={ok} fill={CHART_COLORS[0]} />
            <Scatter data={bad} fill="hsl(var(--destructive))" />
          </ScatterChart>
        </Chart>
      )}
    </div>
  );
}

function CallTooltip({
  active,
  payload,
  metric,
}: {
  active?: boolean;
  payload?: Array<{ payload: { rec: CallPoint } }>;
  metric: "cost" | "tokens";
}) {
  if (!active || !payload?.length) return null;
  const r: CallPoint = payload[0].payload.rec;
  return (
    <div className="rounded-md border bg-background p-2 text-xs shadow-md space-y-0.5">
      <div className="font-medium">{r.model ?? "—"}</div>
      <div className="text-muted-foreground">{new Date(r.started_at).toLocaleString("zh-TW")}</div>
      <div>狀態：{r.outcome}{r.status_code ? `（${r.status_code}）` : ""}</div>
      <div>tokens：{r.total_tokens != null ? fmtInt.format(r.total_tokens) : "—"}</div>
      <div>
        花費：{r.cost_usd != null ? fmtUsd(Number(r.cost_usd)) : "未定價"}
        {r.unit && r.unit !== "token" ? `（${r.quantity ?? "?"} ${r.unit}）` : ""}
      </div>
      {metric === "cost" && r.cost_usd == null && (
        <div className="text-muted-foreground">（未計入花費軸）</div>
      )}
    </div>
  );
}
