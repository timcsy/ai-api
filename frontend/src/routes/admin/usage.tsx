import { useQuery } from "@tanstack/react-query";
import * as React from "react";
import { useSearchParams } from "react-router-dom";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/use-toast";
import { UsageCharts } from "@/components/admin-usage-charts";
import { TimeRangeSelect } from "@/components/time-range-select";
import { ApiError, api } from "@/lib/api-client";
import { apiBlob, triggerDownload } from "@/lib/download";
import { type RangePreset, type TimeRange } from "@/lib/time-range";

interface UsageItem {
  group_key: string;
  display_name: string | null;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  reasoning_tokens: number;
  cached_tokens: number;
  total_cost_usd: number;
  call_count: number;
}

interface UsageResponse {
  from: string;
  to: string;
  group_by: string;
  items: UsageItem[];
}

interface TagMembersResponse {
  tag: string;
  members: UsageItem[];
}

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function thirtyDaysAgo(): string {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return isoDate(d);
}

export function AdminUsagePage() {
  const [params, setParams] = useSearchParams();
  const { toast } = useToast();

  const from = params.get("from") ?? thirtyDaysAgo();
  const to = params.get("to") ?? isoDate(new Date());
  const groupBy = (params.get("group_by") ?? "member") as "member" | "allocation" | "model" | "tag";
  const serviceOnly = params.get("service_only") === "true";

  const fromIso = `${from}T00:00:00Z`;
  const toIso = `${to}T23:59:59Z`;

  // Phase 14 US3: a shared <TimeRangeSelect> drives from/to (stored in the URL so
  // the range survives reloads/sharing). Default preset is 自訂 to preserve the
  // page's historical explicit-date behaviour.
  const range: TimeRange = {
    preset: (params.get("preset") as RangePreset | null) ?? "custom",
    from,
    to,
  };
  const onRangeChange = (next: TimeRange) => {
    setParams((prev) => {
      const n = new URLSearchParams(prev);
      n.set("preset", next.preset);
      n.set("from", next.from);
      n.set("to", next.to);
      return n;
    });
  };

  const setParam = (key: string, value: string | null) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value === null) next.delete(key);
      else next.set(key, value);
      return next;
    });
  };

  const query = useQuery<UsageResponse, ApiError>({
    queryKey: ["admin", "usage", { from, to, groupBy, serviceOnly }],
    queryFn: () => {
      const sp = new URLSearchParams();
      sp.set("from", fromIso);
      sp.set("to", toIso);
      sp.set("group_by", groupBy);
      if (serviceOnly) sp.set("service_only", "true");
      return api<UsageResponse>(`/admin/usage?${sp.toString()}`);
    },
  });

  const download = async (format: "csv" | "json") => {
    try {
      const sp = new URLSearchParams();
      sp.set("from", fromIso);
      sp.set("to", toIso);
      sp.set("group_by", groupBy);
      if (serviceOnly) sp.set("service_only", "true");
      const blob = await apiBlob(`/admin/usage.${format}?${sp.toString()}`);
      triggerDownload(`usage-${from}-${to}.${format}`, blob);
    } catch (err) {
      toast({
        title: "下載失敗",
        description: err instanceof Error ? err.message : String(err),
        variant: "destructive",
      });
    }
  };

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-3xl font-bold">用量統計</h1>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void download("csv")}>
            下載 CSV
          </Button>
          <Button variant="outline" onClick={() => void download("json")}>
            下載 JSON
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3 p-4 bg-card rounded-lg border">
        <TimeRangeSelect value={range} onChange={onRangeChange} />
        <div>
          <Label htmlFor="group_by">分組</Label>
          <Select value={groupBy} onValueChange={(v) => setParam("group_by", v)}>
            <SelectTrigger id="group_by" className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="member">依成員</SelectItem>
              <SelectItem value="allocation">依分配</SelectItem>
              <SelectItem value="model">依模型</SelectItem>
              <SelectItem value="tag">依標籤（班級／群組）</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2 pl-3">
          <Switch
            id="service_only"
            checked={serviceOnly}
            onCheckedChange={(checked) => setParam("service_only", checked ? "true" : null)}
          />
          <Label htmlFor="service_only">只看服務型</Label>
        </div>
      </div>

      {/* Phase 14 US2: provider donut + weekday×hour heatmap, sharing this page's range. */}
      <UsageCharts fromIso={fromIso} toIso={toIso} />

      {groupBy === "tag" && (
        <Alert>
          <AlertDescription>
            成員可同時掛多個標籤，各標籤的加總<strong>可能重複計算</strong>、不等於平台總用量。
            點一列可展開該標籤的成員明細。
          </AlertDescription>
        </Alert>
      )}

      {query.isLoading && <p className="text-muted-foreground">載入中…</p>}
      {query.error && (
        <Alert variant="destructive">
          <AlertDescription>
            {query.error.code === "invalid_time_range"
              ? "時間區間不合法"
              : query.error.message}
          </AlertDescription>
        </Alert>
      )}

      {query.data && (
        <Table className="responsive-table">
          <TableHeader>
            <TableRow>
              <TableHead>
                {groupBy === "member" && "成員"}
                {groupBy === "allocation" && "分配"}
                {groupBy === "model" && "模型"}
                {groupBy === "tag" && "Tag"}
              </TableHead>
              <TableHead className="text-right">輸入 tokens</TableHead>
              <TableHead className="text-right">輸出 tokens</TableHead>
              <TableHead className="text-right">推理 tokens</TableHead>
              <TableHead className="text-right">快取 tokens</TableHead>
              <TableHead className="text-right">總 tokens</TableHead>
              <TableHead className="text-right">費用 (USD)</TableHead>
              <TableHead className="text-right">呼叫次數</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {query.data.items.map((it) =>
              groupBy === "tag" ? (
                <TagRow key={it.group_key} item={it} fromIso={fromIso} toIso={toIso} />
              ) : (
                <TableRow key={it.group_key}>
                  <TableCell className="font-medium" data-label="對象"><span className="block max-w-[160px] truncate">{it.display_name ?? it.group_key}</span></TableCell>
                  <TableCell className="text-right" data-label="輸入 tokens">{it.prompt_tokens.toLocaleString()}</TableCell>
                  <TableCell className="text-right" data-label="輸出 tokens">{it.completion_tokens.toLocaleString()}</TableCell>
                  <TableCell className="text-right text-muted-foreground" data-label="推理 tokens">{it.reasoning_tokens.toLocaleString()}</TableCell>
                  <TableCell className="text-right text-muted-foreground" data-label="快取 tokens">{it.cached_tokens.toLocaleString()}</TableCell>
                  <TableCell className="text-right" data-label="總 tokens">{it.total_tokens.toLocaleString()}</TableCell>
                  <TableCell className="text-right" data-label="費用 (USD)">${it.total_cost_usd.toFixed(4)}</TableCell>
                  <TableCell className="text-right" data-label="呼叫次數">{it.call_count}</TableCell>
                </TableRow>
              ),
            )}
            {query.data.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                  此區間沒有使用紀錄
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function TagRow({ item, fromIso, toIso }: { item: UsageItem; fromIso: string; toIso: string }) {
  const [open, setOpen] = React.useState(false);
  const drill = useQuery<TagMembersResponse, ApiError>({
    queryKey: ["admin", "usage", "tag-members", item.group_key, fromIso, toIso],
    enabled: open,
    queryFn: () => {
      const sp = new URLSearchParams({ from: fromIso, to: toIso });
      return api<TagMembersResponse>(
        `/admin/usage/tag/${encodeURIComponent(item.group_key)}/members?${sp.toString()}`,
      );
    },
  });

  return (
    <>
      <TableRow className="cursor-pointer hover:bg-muted/50" onClick={() => setOpen((v) => !v)}>
        <TableCell className="font-medium" data-label="Tag">
          {open ? "▾ " : "▸ "}
          {item.group_key}
        </TableCell>
        <TableCell className="text-right" data-label="輸入 tokens">{item.prompt_tokens.toLocaleString()}</TableCell>
        <TableCell className="text-right" data-label="輸出 tokens">{item.completion_tokens.toLocaleString()}</TableCell>
        <TableCell className="text-right text-muted-foreground" data-label="推理 tokens">{item.reasoning_tokens.toLocaleString()}</TableCell>
        <TableCell className="text-right text-muted-foreground" data-label="快取 tokens">{item.cached_tokens.toLocaleString()}</TableCell>
        <TableCell className="text-right" data-label="總 tokens">{item.total_tokens.toLocaleString()}</TableCell>
        <TableCell className="text-right" data-label="費用 (USD)">${item.total_cost_usd.toFixed(4)}</TableCell>
        <TableCell className="text-right" data-label="呼叫次數">{item.call_count}</TableCell>
      </TableRow>
      {open && (
        <TableRow>
          <TableCell colSpan={8} className="bg-muted/30 p-0">
            <div className="p-3">
              <div className="mb-1 text-xs text-muted-foreground">
                {item.group_key} 的成員明細
              </div>
              {drill.isLoading && <p className="text-sm text-muted-foreground">載入中…</p>}
              {drill.data && drill.data.members.length === 0 && (
                <p className="text-sm text-muted-foreground">此 tag 在區間內無用量。</p>
              )}
              {drill.data && drill.data.members.length > 0 && (
                <table className="w-full text-sm block overflow-x-auto sm:table">
                  <tbody>
                    {drill.data.members.map((m) => (
                      <tr key={m.group_key} className="border-t border-border/50">
                        <td className="py-1">{m.display_name ?? m.group_key}</td>
                        <td className="py-1 text-right">{m.total_tokens.toLocaleString()} tokens</td>
                        <td className="py-1 text-right">${m.total_cost_usd.toFixed(4)}</td>
                        <td className="py-1 text-right">{m.call_count} 次</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}
