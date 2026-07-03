import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { PerCallScatter, type CallPoint } from "@/components/per-call-scatter";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { TimeRangeSelect } from "@/components/time-range-select";
import { ApiError, api } from "@/lib/api-client";
import { presetRange, rangeToIso } from "@/lib/time-range";

interface Rec extends CallPoint {
  request_id: string;
  subject?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  error_message?: string | null;
}
interface AdminMember { id: string; email: string }

const fmtInt = new Intl.NumberFormat("zh-TW");
const fmtUsd = (n: number) => `$${n.toFixed(n < 1 ? 4 : 2)}`;

const LIMIT = 200;

export function AdminRecordsPage() {
  const [range, setRange] = React.useState(() => presetRange("week"));
  const [memberId, setMemberId] = React.useState<string>("");
  const [outcome, setOutcome] = React.useState<string>("");
  const { fromIso, toIso } = rangeToIso(range);

  const members = useQuery<AdminMember[], ApiError>({
    queryKey: ["admin", "members"],
    queryFn: () => api<AdminMember[]>("/admin/members"),
  });

  const params = React.useMemo(() => {
    const p = new URLSearchParams();
    p.set("from", fromIso);
    p.set("to", toIso);
    if (memberId) p.set("member_id", memberId);
    if (outcome) p.set("outcome", outcome);
    p.set("limit", String(LIMIT));
    return p.toString();
  }, [fromIso, toIso, memberId, outcome]);

  const q = useQuery<{ items: Rec[]; next_before: string | null }, ApiError>({
    queryKey: ["admin", "records", params],
    queryFn: () => api(`/admin/records?${params}`),
  });

  const items = q.data?.items ?? [];

  return (
    <div className="container mx-auto py-8 space-y-5">
      <h1 className="text-2xl font-bold">逐筆記錄</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 border rounded-md p-3 items-end">
        <div className="col-span-2 md:col-span-1">
          <Label className="text-xs">時間範圍</Label>
          <TimeRangeSelect value={range} onChange={setRange} />
        </div>
        <div>
          <Label className="text-xs">成員</Label>
          <Select value={memberId || "all"} onValueChange={(v) => setMemberId(v === "all" ? "" : v)}>
            <SelectTrigger className="mt-1"><SelectValue placeholder="全部" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部成員</SelectItem>
              {members.data?.map((m) => <SelectItem key={m.id} value={m.id}>{m.email}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs">結果</Label>
          <Select value={outcome || "all"} onValueChange={(v) => setOutcome(v === "all" ? "" : v)}>
            <SelectTrigger className="mt-1"><SelectValue placeholder="全部" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部</SelectItem>
              <SelectItem value="success">僅成功</SelectItem>
              <SelectItem value="upstream_error">僅上游錯誤</SelectItem>
              <SelectItem value="rejected_quarantined">僅被隔離擋下</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-base">逐筆散點</CardTitle></CardHeader>
        <CardContent><PerCallScatter records={items} /></CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        共 {items.length} 筆（此區間；最多 {LIMIT}）{q.data?.next_before && "，還有更多——請縮小時間範圍"}
      </p>

      <Table className="responsive-table">
        <TableHeader>
          <TableRow>
            <TableHead>時間</TableHead>
            <TableHead>成員</TableHead>
            <TableHead>模型</TableHead>
            <TableHead className="text-right">tokens</TableHead>
            <TableHead className="text-right">花費</TableHead>
            <TableHead>狀態</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((r) => (
            <TableRow key={r.id}>
              <TableCell className="text-xs" data-label="時間">{new Date(r.started_at).toLocaleString("zh-TW")}</TableCell>
              <TableCell className="text-xs" data-label="成員">{r.subject ?? "—"}</TableCell>
              <TableCell data-label="模型">{r.model ?? "—"}</TableCell>
              <TableCell className="text-right" data-label="tokens">{r.total_tokens != null ? fmtInt.format(r.total_tokens) : "—"}</TableCell>
              <TableCell className="text-right" data-label="花費">
                {r.cost_usd != null ? fmtUsd(Number(r.cost_usd)) : (r.unit && r.unit !== "token" ? `${r.quantity ?? "?"} ${r.unit}` : "未定價")}
              </TableCell>
              <TableCell data-label="狀態">
                <span className={r.outcome === "success" ? "" : "text-destructive"}>
                  {r.outcome}{r.status_code ? `（${r.status_code}）` : ""}
                </span>
                {r.error_message && <div className="text-xs text-muted-foreground truncate max-w-[240px]">{r.error_message}</div>}
              </TableCell>
            </TableRow>
          ))}
          {items.length === 0 && (
            <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground py-8">此區間沒有呼叫記錄</TableCell></TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
