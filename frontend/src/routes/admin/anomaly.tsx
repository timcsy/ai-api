import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { ApiError, api } from "@/lib/api-client";

interface AnomalyConfig {
  auto_quarantine_enabled: boolean;
  pause_until: string | null;
  effective_enforcing: boolean;
  status: "enabled" | "disabled" | "paused";
  thresholds: {
    threshold_multiplier: number;
    min_calls: number;
    absolute_cold_start: number;
    baseline_min_calls: number;
  };
  updated_at: string | null;
  updated_by: string | null;
}

type Update = Record<string, unknown>;

export function AdminAnomalyPage() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const cfgQuery = useQuery<AnomalyConfig, ApiError>({
    queryKey: ["admin", "anomaly", "config"],
    queryFn: () => api<AnomalyConfig>("/admin/anomaly/config"),
  });

  const mut = useMutation<AnomalyConfig, ApiError, Update>({
    mutationFn: (body) =>
      api<AnomalyConfig>("/admin/anomaly/config", { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: () => {
      toast({ title: "已儲存異常偵測設定" });
      qc.invalidateQueries({ queryKey: ["admin", "anomaly", "config"] });
    },
    onError: (e) => toast({ title: "儲存失敗", description: e.message, variant: "destructive" }),
  });

  const cfg = cfgQuery.data;
  const [pauseLocal, setPauseLocal] = React.useState<string>("");
  const [th, setTh] = React.useState({ mult: "", min: "", abs: "", base: "" });
  React.useEffect(() => {
    if (cfg)
      setTh({
        mult: String(cfg.thresholds.threshold_multiplier),
        min: String(cfg.thresholds.min_calls),
        abs: String(cfg.thresholds.absolute_cold_start),
        base: String(cfg.thresholds.baseline_min_calls),
      });
  }, [cfg?.thresholds]);

  const statusBadge = () => {
    if (!cfg) return null;
    if (cfg.status === "enabled")
      return <Badge>啟用中</Badge>;
    if (cfg.status === "paused")
      return <Badge variant="outline">暫停中（至 {cfg.pause_until && new Date(cfg.pause_until).toLocaleString("zh-TW")}）</Badge>;
    return <Badge variant="destructive">已停用</Badge>;
  };

  return (
    <div className="container mx-auto py-8 space-y-6">
      <h1 className="text-2xl font-bold">異常偵測</h1>
      <p className="text-sm text-muted-foreground">
        系統會把短時間用量異常暴增的分配自動隔離（保護共用額度）。辦研習或已知高用量活動前，可在此**暫停或關閉**自動隔離；
        額度上限（token／花費）仍會照常保護，故暫停期間風險有限。
      </p>

      {cfgQuery.error && (
        <Alert variant="destructive"><AlertDescription>{cfgQuery.error.message}</AlertDescription></Alert>
      )}

      {cfg && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-3">自動隔離 {statusBadge()}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* 開關 */}
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant={cfg.auto_quarantine_enabled ? "destructive" : "default"}
                disabled={mut.isPending}
                onClick={() => mut.mutate({ auto_quarantine_enabled: !cfg.auto_quarantine_enabled })}
              >
                {cfg.auto_quarantine_enabled ? "停用自動隔離" : "啟用自動隔離"}
              </Button>
              <span className="text-xs text-muted-foreground">
                停用後偵測器仍會記錄異常，但不會隔離任何人。
              </span>
            </div>

            {/* 暫停到某時間（自動恢復） */}
            <div className="rounded-md border p-3 space-y-2">
              <Label htmlFor="pause-until">暫停到此時間（到期自動恢復）</Label>
              <div className="flex flex-wrap items-center gap-2">
                <Input
                  id="pause-until"
                  type="datetime-local"
                  className="max-w-[220px]"
                  value={pauseLocal}
                  onChange={(e) => setPauseLocal(e.target.value)}
                />
                <Button
                  variant="outline"
                  disabled={!pauseLocal || mut.isPending}
                  onClick={() => mut.mutate({ pause_until: new Date(pauseLocal).toISOString() })}
                >
                  暫停到此時間
                </Button>
                {cfg.pause_until && (
                  <Button variant="ghost" disabled={mut.isPending} onClick={() => mut.mutate({ clear_pause: true })}>
                    清除暫停
                  </Button>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                例：研習當天設到「研習結束時間」，期間不隔離、之後自動恢復，不怕忘記關回。
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {cfg && (
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-base">偵測門檻</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="th-mult">比例倍數（近1h ≥ baseline/hr × 此值 → 隔離）</Label>
                <Input id="th-mult" inputMode="decimal" value={th.mult} onChange={(e) => setTh({ ...th, mult: e.target.value })} />
              </div>
              <div>
                <Label htmlFor="th-min">最小觸發呼叫數（近1h 低於此不評估）</Label>
                <Input id="th-min" inputMode="numeric" value={th.min} onChange={(e) => setTh({ ...th, min: e.target.value })} />
              </div>
              <div>
                <Label htmlFor="th-abs">絕對門檻（近1h 達此值一律隔離）</Label>
                <Input id="th-abs" inputMode="numeric" value={th.abs} onChange={(e) => setTh({ ...th, abs: e.target.value })} />
              </div>
              <div>
                <Label htmlFor="th-base">baseline 最小可信樣本數</Label>
                <Input id="th-base" inputMode="numeric" value={th.base} onChange={(e) => setTh({ ...th, base: e.target.value })} />
                <p className="mt-1 text-xs text-muted-foreground">baseline 樣本低於此 → 不套比例規則、只用絕對門檻（避免剛遷移/新站/衝量誤判）。</p>
              </div>
            </div>
            <Button
              disabled={mut.isPending}
              onClick={() =>
                mut.mutate({
                  threshold_multiplier: Number(th.mult),
                  min_calls: Number(th.min),
                  absolute_cold_start: Number(th.abs),
                  baseline_min_calls: Number(th.base),
                })
              }
            >
              儲存門檻
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
