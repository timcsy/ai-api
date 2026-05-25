import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiError, api } from "@/lib/api-client";

interface AuditRow {
  id: string;
  event_type: string;
  actor_type: string;
  actor_id: string | null;
  target_type: string | null;
  target_id: string | null;
  source_ip: string | null;
  request_id: string | null;
  created_at: string;
  details: Record<string, unknown> | null;
  redacted_message: string | null;
}

const ACTOR_TYPES = ["admin", "member", "system", "anonymous"] as const;

export function AdminAuditPage() {
  const [eventType, setEventType] = React.useState<string>("");
  const [actorType, setActorType] = React.useState<string>("");
  const [actorId, setActorId] = React.useState("");
  const [targetType, setTargetType] = React.useState("");
  const [targetId, setTargetId] = React.useState("");

  const eventsQuery = useQuery<string[], ApiError>({
    queryKey: ["admin", "audit-event-types"],
    queryFn: () => api<string[]>("/admin/audit/event-types"),
  });

  const params = React.useMemo(() => {
    const p = new URLSearchParams();
    if (eventType) p.set("event_type", eventType);
    if (actorType) p.set("actor_type", actorType);
    if (actorId) p.set("actor_id", actorId);
    if (targetType) p.set("target_type", targetType);
    if (targetId) p.set("target_id", targetId);
    p.set("limit", "100");
    return p.toString();
  }, [eventType, actorType, actorId, targetType, targetId]);

  const query = useQuery<{ rows: AuditRow[]; limit: number; offset: number }, ApiError>({
    queryKey: ["admin", "audit", params],
    queryFn: () => api(`/admin/audit?${params}`),
  });

  return (
    <div className="container mx-auto py-8 max-w-7xl space-y-4">
      <h1 className="text-2xl font-bold">稽核紀錄</h1>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 border rounded-md p-3">
        <div>
          <Label className="text-xs">事件型別</Label>
          <Select value={eventType || "all"} onValueChange={(v) => setEventType(v === "all" ? "" : v)}>
            <SelectTrigger className="mt-1"><SelectValue placeholder="全部" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部</SelectItem>
              {eventsQuery.data?.map((e) => (
                <SelectItem key={e} value={e}>{e}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs">操作者型別</Label>
          <Select value={actorType || "all"} onValueChange={(v) => setActorType(v === "all" ? "" : v)}>
            <SelectTrigger className="mt-1"><SelectValue placeholder="全部" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部</SelectItem>
              {ACTOR_TYPES.map((a) => (
                <SelectItem key={a} value={a}>{a}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs">Actor ID</Label>
          <Input className="mt-1" value={actorId} onChange={(e) => setActorId(e.target.value)} />
        </div>
        <div>
          <Label className="text-xs">Target 型別</Label>
          <Input className="mt-1" value={targetType} onChange={(e) => setTargetType(e.target.value)} placeholder="member / allocation / provider_credential ..." />
        </div>
        <div>
          <Label className="text-xs">Target ID</Label>
          <Input className="mt-1" value={targetId} onChange={(e) => setTargetId(e.target.value)} />
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        最近 {query.data?.rows.length ?? 0} 筆（從新到舊；最多 100）
      </p>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>時間</TableHead>
            <TableHead>事件</TableHead>
            <TableHead>操作者</TableHead>
            <TableHead>對象</TableHead>
            <TableHead>細節</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {query.isLoading && (
            <TableRow><TableCell colSpan={5} className="text-muted-foreground">載入中…</TableCell></TableRow>
          )}
          {query.data?.rows.length === 0 && (
            <TableRow><TableCell colSpan={5} className="text-muted-foreground">無符合條件的紀錄。</TableCell></TableRow>
          )}
          {query.data?.rows.map((r) => (
            <TableRow key={r.id}>
              <TableCell className="text-xs whitespace-nowrap">
                {new Date(r.created_at).toLocaleString("zh-TW")}
              </TableCell>
              <TableCell>
                <Badge variant="outline" className="font-mono text-xs">{r.event_type}</Badge>
              </TableCell>
              <TableCell className="text-xs">
                <div>{r.actor_type}</div>
                {r.actor_id && <div className="text-muted-foreground">{r.actor_id}</div>}
              </TableCell>
              <TableCell className="text-xs">
                {r.target_type && <div>{r.target_type}</div>}
                {r.target_id && <div className="text-muted-foreground font-mono">{r.target_id}</div>}
              </TableCell>
              <TableCell className="text-xs">
                {r.details && (
                  <details>
                    <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                      展開
                    </summary>
                    <pre className="bg-muted p-2 mt-1 text-xs overflow-x-auto max-w-md">
                      {JSON.stringify(r.details, null, 2)}
                    </pre>
                  </details>
                )}
                {r.redacted_message && (
                  <p className="text-muted-foreground">{r.redacted_message}</p>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={() => void query.refetch()}>
          重新整理
        </Button>
      </div>
    </div>
  );
}
