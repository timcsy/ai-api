import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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

interface PoolStatus {
  total_T: number;
  reserved: { service: number; locked: number };
  distributable: number;
  pool_member_count: number;
  floor: number;
  settings: { enabled: boolean };
  last_rebalance_at: string | null;
}

interface LogSummary {
  id: string;
  period_yyyymm: string;
  triggered_by: string;
  started_at: string;
  finished_at: string;
  T_before: number;
  T_after: number;
  scanned: number;
  changed: number;
  algorithm_version: string;
}

interface LogDetail extends LogSummary {
  details: Record<string, unknown>;
}

export function AdminQuotaPoolPage() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const [detailLog, setDetailLog] = React.useState<LogDetail | null>(null);

  const statusQuery = useQuery<PoolStatus, ApiError>({
    queryKey: ["admin", "quota-pool", "status"],
    queryFn: () => api<PoolStatus>("/admin/quota-pool/status"),
  });
  const logQuery = useQuery<LogSummary[], ApiError>({
    queryKey: ["admin", "quota-pool", "log"],
    queryFn: () => api<LogSummary[]>("/admin/quota-pool/rebalance-log?limit=20"),
  });

  const rebalanceMut = useMutation({
    mutationFn: () => api<LogSummary>("/admin/quota-pool/rebalance", { method: "POST" }),
    onSuccess: (data) => {
      toast({
        title: "Rebalance 完成",
        description: `scanned=${data.scanned}, changed=${data.changed}`,
      });
      qc.invalidateQueries({ queryKey: ["admin", "quota-pool"] });
    },
    onError: (err: ApiError) => {
      toast({
        title: "Rebalance 失敗",
        description: `${err.code}: ${err.message}`,
        variant: "destructive",
      });
    },
  });

  const status = statusQuery.data;
  const disabled = status?.settings.enabled === false;

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Quota Pool</h1>
        <Button onClick={() => setConfirmOpen(true)} disabled={disabled || rebalanceMut.isPending}>
          {rebalanceMut.isPending ? "Rebalancing…" : "手動 Rebalance"}
        </Button>
      </div>

      {statusQuery.error && (
        <Alert variant="destructive">
          <AlertDescription>{statusQuery.error.message}</AlertDescription>
        </Alert>
      )}

      {disabled && (
        <Alert>
          <AlertDescription>池已停用（T=0）。設定 POOL_TOTAL_TOKENS_PER_MONTH 才能啟用。</AlertDescription>
        </Alert>
      )}

      {status && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">T (total)</CardTitle></CardHeader>
            <CardContent className="text-2xl font-bold">{status.total_T.toLocaleString()}</CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Reserved</CardTitle></CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{(status.reserved.service + status.reserved.locked).toLocaleString()}</div>
              <div className="text-xs text-muted-foreground">service: {status.reserved.service} · locked: {status.reserved.locked}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Distributable</CardTitle></CardHeader>
            <CardContent className="text-2xl font-bold">{status.distributable.toLocaleString()}</CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Pool members</CardTitle></CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{status.pool_member_count}</div>
              <div className="text-xs text-muted-foreground">floor: {status.floor}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {status?.last_rebalance_at && (
        <p className="text-sm text-muted-foreground">
          上次 rebalance：{new Date(status.last_rebalance_at).toLocaleString("zh-TW")}
        </p>
      )}

      <section>
        <h2 className="text-xl font-semibold mb-3">Rebalance log</h2>
        {logQuery.data && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>時間</TableHead>
                <TableHead>Period</TableHead>
                <TableHead>Trigger</TableHead>
                <TableHead className="text-right">Scanned</TableHead>
                <TableHead className="text-right">Changed</TableHead>
                <TableHead className="text-right">T</TableHead>
                <TableHead>Version</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logQuery.data.map((row) => (
                <TableRow
                  key={row.id}
                  className="cursor-pointer"
                  onClick={async () => {
                    const detail = await api<LogDetail>(
                      `/admin/quota-pool/rebalance-log/${row.id}`,
                    );
                    setDetailLog(detail);
                  }}
                >
                  <TableCell className="text-xs">
                    {new Date(row.finished_at).toLocaleString("zh-TW")}
                  </TableCell>
                  <TableCell>{row.period_yyyymm}</TableCell>
                  <TableCell><Badge variant="outline">{row.triggered_by}</Badge></TableCell>
                  <TableCell className="text-right">{row.scanned}</TableCell>
                  <TableCell className="text-right">{row.changed}</TableCell>
                  <TableCell className="text-right">{row.T_after.toLocaleString()}</TableCell>
                  <TableCell>{row.algorithm_version}</TableCell>
                </TableRow>
              ))}
              {logQuery.data.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    尚無 rebalance 紀錄
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
      </section>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>確認手動 Rebalance？</AlertDialogTitle>
            <AlertDialogDescription>
              這會立即重新分配所有池內 allocation 的 quota，並寫入 RebalanceLog。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={() => rebalanceMut.mutate()}>確認執行</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={!!detailLog} onOpenChange={(open) => !open && setDetailLog(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>RebalanceLog {detailLog?.id}</DialogTitle>
            <DialogDescription>{detailLog?.triggered_by} · {detailLog?.period_yyyymm}</DialogDescription>
          </DialogHeader>
          <pre className="bg-muted p-3 rounded text-xs max-h-[400px] overflow-auto">
            {JSON.stringify(detailLog?.details, null, 2)}
          </pre>
          <DialogFooter>
            <Button onClick={() => setDetailLog(null)}>關閉</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
