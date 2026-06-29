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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  config: {
    total_tokens_per_month: number;
    floor_per_allocation: number;
    updated_at: string | null;
    updated_by: string | null;
  };
  suggestion: {
    recent_month_tokens: number;
    pool_members: number;
    suggested_total: number;
    suggested_floor: number;
  };
  warning: string | null;
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
        title: "重新平衡完成",
        description: `scanned=${data.scanned}, changed=${data.changed}`,
      });
      qc.invalidateQueries({ queryKey: ["admin", "quota-pool"] });
    },
    onError: (err: ApiError) => {
      toast({
        title: "重新平衡失敗",
        description: `${err.code}: ${err.message}`,
        variant: "destructive",
      });
    },
  });

  const status = statusQuery.data;
  const disabled = status?.settings.enabled === false;

  // Phase 39: editable pool config (T / floor) + suggestion + validation.
  const [editT, setEditT] = React.useState<string>("");
  const [editFloor, setEditFloor] = React.useState<string>("");
  React.useEffect(() => {
    if (status) {
      setEditT(String(status.config.total_tokens_per_month));
      setEditFloor(String(status.config.floor_per_allocation));
    }
  }, [status?.config.total_tokens_per_month, status?.config.floor_per_allocation]);

  const saveMut = useMutation({
    mutationFn: () =>
      api("/admin/quota-pool/config", {
        method: "PUT",
        body: JSON.stringify({
          total_tokens_per_month: Number(editT),
          floor_per_allocation: Number(editFloor),
        }),
      }),
    onSuccess: () => {
      toast({ title: "已儲存配額池設定", description: "設定於下次再分配生效" });
      qc.invalidateQueries({ queryKey: ["admin", "quota-pool"] });
    },
    onError: (err: ApiError) =>
      toast({ title: "儲存失敗", description: `${err.code}: ${err.message}`, variant: "destructive" }),
  });

  const N = status?.pool_member_count ?? 0;
  const tNum = Number(editT);
  const floorNum = Number(editFloor);
  const validNums =
    Number.isInteger(tNum) && Number.isInteger(floorNum) && tNum >= 0 && floorNum >= 0;
  const meetsFloor = validNums && tNum >= floorNum * N;
  const belowUsage = validNums && status != null && tNum < status.suggestion.recent_month_tokens;

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">配額池監控</h1>
        <Button onClick={() => setConfirmOpen(true)} disabled={disabled || rebalanceMut.isPending}>
          {rebalanceMut.isPending ? "執行中…" : "手動執行再分配"}
        </Button>
      </div>

      {statusQuery.error && (
        <Alert variant="destructive">
          <AlertDescription>{statusQuery.error.message}</AlertDescription>
        </Alert>
      )}

      {disabled && (
        <Alert>
          <AlertDescription>池已停用（總額 T=0）。在下方「配額池設定」填入每月總額即可啟用。</AlertDescription>
        </Alert>
      )}

      {status && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">總配額 T</CardTitle></CardHeader>
            <CardContent className="text-2xl font-bold">{status.total_T.toLocaleString()}</CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">預留</CardTitle></CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{(status.reserved.service + status.reserved.locked).toLocaleString()}</div>
              <div className="text-xs text-muted-foreground">服務型：{status.reserved.service} · 鎖定型：{status.reserved.locked}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">可分配</CardTitle></CardHeader>
            <CardContent className="text-2xl font-bold">{status.distributable.toLocaleString()}</CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">池內成員</CardTitle></CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{status.pool_member_count}</div>
              <div className="text-xs text-muted-foreground">保底：{status.floor}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {status && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">配額池設定</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="pool-T">每月總額 T（tokens）</Label>
                <Input
                  id="pool-T"
                  inputMode="numeric"
                  value={editT}
                  onChange={(e) => setEditT(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="pool-floor">每分配保底（tokens）</Label>
                <Input
                  id="pool-floor"
                  inputMode="numeric"
                  value={editFloor}
                  onChange={(e) => setEditFloor(e.target.value)}
                />
              </div>
            </div>
            {!validNums && <p className="text-sm text-destructive">請輸入 ≥ 0 的整數。</p>}
            {validNums && !meetsFloor && (
              <p className="text-sm text-destructive">
                總額需 ≥ 保底 × 池內成員數（{floorNum.toLocaleString()} × {N} ={" "}
                {(floorNum * N).toLocaleString()}）。
              </p>
            )}
            {belowUsage && (
              <p className="text-sm text-amber-600 dark:text-amber-500">
                ⚠ 總額低於近月用量（{status.suggestion.recent_month_tokens.toLocaleString()}），
                部分使用者本月可能被擋下；仍可儲存。
              </p>
            )}
            <div className="rounded-md border bg-muted/40 p-3 text-sm">
              <div className="font-medium">建議值</div>
              <div className="mt-1 text-muted-foreground">
                近月用量 {status.suggestion.recent_month_tokens.toLocaleString()}；建議總額 ≈{" "}
                {status.suggestion.suggested_total.toLocaleString()}（近月 × 2，留成長空間又封住總量上限）、
                建議保底 ≈ {status.suggestion.suggested_floor.toLocaleString()}（讓零用量成員仍有可用基本額）。
              </div>
              <Button
                variant="outline"
                size="sm"
                className="mt-2"
                onClick={() => {
                  setEditT(String(status.suggestion.suggested_total));
                  setEditFloor(String(status.suggestion.suggested_floor));
                }}
              >
                套用建議
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={() => saveMut.mutate()} disabled={!meetsFloor || saveMut.isPending}>
                {saveMut.isPending ? "儲存中…" : "儲存設定"}
              </Button>
              <span className="text-xs text-muted-foreground">
                設定於下次再分配生效（或按「手動執行再分配」）。池內成員 N＝{N}。
              </span>
            </div>
          </CardContent>
        </Card>
      )}

      {status?.last_rebalance_at && (
        <p className="text-sm text-muted-foreground">
          上次 rebalance：{new Date(status.last_rebalance_at).toLocaleString("zh-TW")}
        </p>
      )}

      <section>
        <h2 className="text-xl font-semibold mb-3">再分配紀錄</h2>
        {logQuery.data && (
          <Table className="responsive-table">
            <TableHeader>
              <TableRow>
                <TableHead>時間</TableHead>
                <TableHead>期間</TableHead>
                <TableHead>觸發</TableHead>
                <TableHead className="text-right">掃描</TableHead>
                <TableHead className="text-right">變更</TableHead>
                <TableHead className="text-right">T 值</TableHead>
                <TableHead>演算法版本</TableHead>
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
                  <TableCell className="text-xs" data-label="時間">
                    {new Date(row.finished_at).toLocaleString("zh-TW")}
                  </TableCell>
                  <TableCell data-label="期間">{row.period_yyyymm}</TableCell>
                  <TableCell data-label="觸發"><Badge variant="outline">{row.triggered_by}</Badge></TableCell>
                  <TableCell className="text-right" data-label="掃描">{row.scanned}</TableCell>
                  <TableCell className="text-right" data-label="變更">{row.changed}</TableCell>
                  <TableCell className="text-right" data-label="T 值">{row.T_after.toLocaleString()}</TableCell>
                  <TableCell data-label="演算法版本">{row.algorithm_version}</TableCell>
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
            <AlertDialogTitle>確認手動執行再分配？</AlertDialogTitle>
            <AlertDialogDescription>
              這會立即重新分配所有池內分配的配額，並寫入重新平衡記錄。
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
            <DialogTitle>重新平衡記錄 {detailLog?.id}</DialogTitle>
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
