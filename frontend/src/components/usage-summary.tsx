import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, api } from "@/lib/api-client";

type Range = "month" | "7d" | "30d";

interface BreakdownItem {
  group_key: string;
  display_name: string | null;
  total_tokens: number;
  total_cost_usd: number;
  call_count: number;
}

interface UsageResp {
  from: string;
  to: string;
  summary: {
    total_tokens: number;
    prompt_tokens: number;
    completion_tokens: number;
    total_cost_usd: number;
    call_count: number;
    has_unpriced: boolean;
  };
  breakdown?: BreakdownItem[];
}

const RANGE_LABEL: Record<Range, string> = { month: "本月", "7d": "近 7 天", "30d": "近 30 天" };

function rangeQuery(r: Range): string {
  if (r === "month") return "group_by=model"; // server defaults to current month
  const days = r === "7d" ? 7 : 30;
  const to = new Date();
  const from = new Date(to.getTime() - days * 86_400_000);
  return `group_by=model&from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}`;
}

const money = (n: number) => `$${n.toFixed(4)}`;

/** Member's own aggregate usage. Self-contained; degrades quietly on error so it
 * never breaks the dashboard. */
export function UsageSummary() {
  const [range, setRange] = React.useState<Range>("month");
  const q = useQuery<UsageResp, ApiError>({
    queryKey: ["me", "usage", range],
    queryFn: () => api<UsageResp>(`/me/usage?${rangeQuery(range)}`),
  });

  if (q.isError) return null; // quiet degrade — usage is supplementary
  const s = q.data?.summary;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">用量總覽</CardTitle>
            <CardDescription>你跨所有分配的用量（只看自己）</CardDescription>
          </div>
          <div className="flex gap-1 shrink-0">
            {(["month", "7d", "30d"] as Range[]).map((r) => (
              <Button
                key={r}
                size="sm"
                variant={r === range ? "default" : "outline"}
                onClick={() => setRange(r)}
              >
                {RANGE_LABEL[r]}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {q.isLoading && <p className="text-sm text-muted-foreground">載入中…</p>}
        {s && (
          <>
            <div className="grid grid-cols-3 gap-4">
              <Stat label="總 tokens" value={s.total_tokens.toLocaleString()} />
              <Stat label="估算花費" value={money(s.total_cost_usd)} />
              <Stat label="呼叫次數" value={s.call_count.toLocaleString()} />
            </div>
            {s.has_unpriced && (
              <p className="mt-2 text-xs text-amber-700">⚠ 含未定價項目，花費為低估</p>
            )}
            {q.data?.breakdown && q.data.breakdown.length > 0 && (
              <div className="mt-4 space-y-1">
                <div className="grid grid-cols-3 border-b pb-1 text-xs font-medium text-muted-foreground">
                  <span>Model</span>
                  <span className="text-right">tokens</span>
                  <span className="text-right">花費</span>
                </div>
                {q.data.breakdown.map((b) => (
                  <div key={b.group_key} className="grid grid-cols-3 py-1 text-sm">
                    <span className="truncate font-mono text-xs">{b.group_key}</span>
                    <span className="text-right tabular-nums">{b.total_tokens.toLocaleString()}</span>
                    <span className="text-right tabular-nums">{money(b.total_cost_usd)}</span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-2xl font-bold tabular-nums">{value}</div>
    </div>
  );
}
