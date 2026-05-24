import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/use-toast";
import { ApiError, api } from "@/lib/api-client";
import { copyToClipboard } from "@/lib/clipboard";

interface LogSummary {
  id: string;
  period_yyyymm: string;
  triggered_by: string;
  finished_at: string;
  T_after: number;
  scanned: number;
  changed: number;
  algorithm_version: string;
}

interface LogDetail extends LogSummary {
  started_at: string;
  T_before: number;
  details: Record<string, unknown>;
}

export function AdminRebalanceLogListPage() {
  const query = useQuery<LogSummary[], ApiError>({
    queryKey: ["admin", "quota-pool", "log", { limit: 100 }],
    queryFn: () => api<LogSummary[]>("/admin/quota-pool/rebalance-log?limit=100"),
  });

  return (
    <div className="container mx-auto py-8 space-y-6">
      <h1 className="text-3xl font-bold">再分配紀錄</h1>

      {query.error && (
        <Alert variant="destructive">
          <AlertDescription>{query.error.message}</AlertDescription>
        </Alert>
      )}

      {query.data && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>時間</TableHead>
              <TableHead>期間</TableHead>
              <TableHead>觸發</TableHead>
              <TableHead className="text-right">掃描 / 變更</TableHead>
              <TableHead className="text-right">T 值</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {query.data.map((row) => (
              <TableRow key={row.id}>
                <TableCell className="text-xs">
                  {new Date(row.finished_at).toLocaleString("zh-TW")}
                </TableCell>
                <TableCell>{row.period_yyyymm}</TableCell>
                <TableCell><Badge variant="outline">{row.triggered_by}</Badge></TableCell>
                <TableCell className="text-right">{row.scanned} / {row.changed}</TableCell>
                <TableCell className="text-right">{row.T_after.toLocaleString()}</TableCell>
                <TableCell>
                  <Button asChild variant="ghost" size="sm">
                    <Link to={`/admin/rebalance-log/${row.id}`}>詳細</Link>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

export function AdminRebalanceLogDetailPage() {
  const { id = "" } = useParams<{ id: string }>();
  const { toast } = useToast();

  const query = useQuery<LogDetail, ApiError>({
    queryKey: ["admin", "quota-pool", "log", id],
    queryFn: () => api<LogDetail>(`/admin/quota-pool/rebalance-log/${id}`),
    enabled: !!id,
  });

  if (query.error?.status === 404) {
    return (
      <div className="container mx-auto py-10 max-w-md text-center space-y-4">
        <h1 className="text-xl font-semibold">找不到 RebalanceLog</h1>
        <Button asChild variant="outline">
          <Link to="/admin/rebalance-log">回列表</Link>
        </Button>
      </div>
    );
  }
  if (!query.data) return <p className="container mx-auto py-8 text-muted-foreground">載入中…</p>;

  const log = query.data;
  const jsonText = JSON.stringify(log, null, 2);

  return (
    <div className="container mx-auto py-8 space-y-6 max-w-4xl">
      <Link to="/admin/rebalance-log" className="text-sm text-muted-foreground hover:underline">
        ← 回列表
      </Link>
      <h1 className="text-2xl font-bold">{log.id}</h1>
      <div className="flex gap-2 flex-wrap text-sm">
        <Badge>{log.triggered_by}</Badge>
        <Badge variant="outline">{log.period_yyyymm}</Badge>
        <span className="text-muted-foreground">scanned={log.scanned}, changed={log.changed}</span>
      </div>
      <div className="flex justify-end">
        <Button
          variant="outline"
          size="sm"
          onClick={async () => {
            const ok = await copyToClipboard(jsonText);
            toast({ title: ok ? "已複製 JSON" : "複製失敗" });
          }}
        >
          複製 JSON
        </Button>
      </div>
      <pre className="bg-muted p-3 rounded text-xs overflow-auto max-h-[600px]">{jsonText}</pre>
    </div>
  );
}
