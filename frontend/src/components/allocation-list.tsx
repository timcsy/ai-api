import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/use-toast";
import { ApiError, api } from "@/lib/api-client";
import { copyToClipboard } from "@/lib/clipboard";
import { per1kToPer1m } from "@/lib/price-format";

interface Allocation {
  id: string;
  member_id: string;
  subject_snapshot: string;
  resource_model: string;
  display_name?: string | null;
  status: string;
  created_at: string;
  revoked_at: string | null;
  token_prefix: string;
  quota_tokens_per_month?: number | null;
  price?: { input_per_1k: string; output_per_1k: string; cached_input_per_1k?: string } | null;
}

interface UsageByAlloc {
  breakdown?: { group_key: string; total_tokens: number }[];
}

interface ClaimableModel {
  slug: string;
  display_name: string;
  provider: string;
  default_quota: number | null;
  state: "claimable" | "already_claimed" | "reclaim_locked";
}

/**
 * Phase 22: extracted from the old single-scroll dashboard. The member's
 * "可自助領取" + "我的分配" sections, now the body of the 分配 page.
 */
export function AllocationList() {
  const [includeRevoked, setIncludeRevoked] = React.useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [tokenDialog, setTokenDialog] = React.useState<string | null>(null);

  const query = useQuery<Allocation[], ApiError>({
    queryKey: ["me", "allocations"],
    queryFn: () => api<Allocation[]>("/me/allocations"),
  });

  // This-month usage per allocation, for the quota view on each card. Degrades
  // quietly (empty map) on error — quota line just falls back to "—".
  const usageByAlloc = useQuery<UsageByAlloc, ApiError>({
    queryKey: ["me", "usage", "by-allocation"],
    queryFn: () => api<UsageByAlloc>("/me/usage?group_by=allocation"),
  });
  const usedByAlloc = React.useMemo(() => {
    const m = new Map<string, number>();
    for (const b of usageByAlloc.data?.breakdown ?? []) m.set(b.group_key, b.total_tokens);
    return m;
  }, [usageByAlloc.data]);

  const claimableQuery = useQuery<ClaimableModel[], ApiError>({
    queryKey: ["me", "claimable-models"],
    queryFn: () => api<ClaimableModel[]>("/me/claimable-models"),
  });

  const claimMut = useMutation<{ token: string }, ApiError, string>({
    mutationFn: (model) =>
      api<{ token: string }>("/me/allocations", {
        method: "POST",
        body: JSON.stringify({ model }),
      }),
    onSuccess: (r) => {
      setTokenDialog(r.token);
      queryClient.invalidateQueries({ queryKey: ["me", "allocations"] });
      queryClient.invalidateQueries({ queryKey: ["me", "claimable-models"] });
    },
    onError: (e) => toast({ title: "領取失敗", description: e.message, variant: "destructive" }),
  });

  const filtered = React.useMemo(() => {
    if (!query.data) return [];
    return includeRevoked
      ? query.data
      : query.data.filter((a) => a.status === "active");
  }, [query.data, includeRevoked]);

  return (
    <>
      {(claimableQuery.data?.length ?? 0) > 0 && (
        <section className="space-y-3">
          <h2 className="text-xl font-semibold">可自助領取</h2>
          <p className="text-sm text-muted-foreground">
            以下 model 已開放自助領取且你被允許使用。按「領取憑證」即可取得一張可呼叫的 token。
          </p>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {claimableQuery.data?.map((m) => (
              <Link key={m.slug} to={`/catalog/${m.slug}`} className="block">
                <Card className="hover:bg-accent transition-colors cursor-pointer">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{m.display_name}</CardTitle>
                  <CardDescription className="font-mono text-xs">{m.slug}</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs text-muted-foreground">
                    月配額 {m.default_quota?.toLocaleString() ?? "—"}
                  </span>
                  {m.state === "claimable" && (
                    <Button
                      size="sm"
                      disabled={claimMut.isPending}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        claimMut.mutate(m.slug);
                      }}
                    >
                      領取憑證
                    </Button>
                  )}
                  {m.state === "already_claimed" && (
                    <Badge variant="secondary">已領取</Badge>
                  )}
                  {m.state === "reclaim_locked" && (
                    <Badge variant="outline" className="shrink-0 whitespace-nowrap text-amber-700 border-amber-500">
                      需 admin 解鎖
                    </Badge>
                  )}
                </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">我的分配</h2>
          <div className="flex items-center gap-2">
            <Switch
              id="include-revoked"
              checked={includeRevoked}
              onCheckedChange={setIncludeRevoked}
            />
            <Label htmlFor="include-revoked">含已撤回</Label>
          </div>
        </div>

        {query.isLoading && <p className="text-muted-foreground">載入中…</p>}

        {query.error && (
          <Alert variant="destructive">
            <AlertDescription className="flex items-center justify-between">
              <span>無法載入分配：{query.error.message}</span>
              <Button size="sm" variant="outline" onClick={() => void query.refetch()}>
                重試
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {query.data && filtered.length === 0 && (
          <Card>
            <CardContent className="py-8 space-y-4 text-sm text-muted-foreground">
              <p className="text-center">尚未獲得任何分配。三步開始使用：</p>
              <ol className="mx-auto max-w-md space-y-2">
                <li><span className="font-semibold text-foreground">① 領取憑證</span>——上方「可自助領取」按「領取憑證」，或請管理員分配。</li>
                <li><span className="font-semibold text-foreground">② 複製 token</span>——領取/建立時一次性顯示，立即複製保存。</li>
                <li><span className="font-semibold text-foreground">③ 貼進 Authorization</span>——呼叫 API 時放於 <code className="text-xs">Authorization: Bearer &lt;token&gt;</code>，端點見「金鑰」頁。</li>
              </ol>
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {filtered.map((a) => (
            <Link key={a.id} to={`/dashboard/allocations/${a.id}`}>
              <Card className="hover:bg-accent transition-colors cursor-pointer">
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-lg min-w-0 truncate">{a.display_name ?? a.resource_model}</CardTitle>
                    <Badge variant={a.status === "active" ? "default" : "secondary"} className="shrink-0">
                      {a.status}
                    </Badge>
                  </div>
                  <CardDescription className="space-y-0.5 text-xs">
                    <span className="block">
                      呼叫用 model 名稱：<span className="font-mono text-foreground">{a.resource_model}</span>
                    </span>
                    <span className="block">
                      憑證：<span className="font-mono">{a.token_prefix}…</span>
                    </span>
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-xs text-muted-foreground">
                  {a.status === "active" && (
                    a.quota_tokens_per_month != null ? (
                      <div className="space-y-1">
                        <div className="text-foreground">
                          本月已用 {(usedByAlloc.get(a.id) ?? 0).toLocaleString()} / {a.quota_tokens_per_month.toLocaleString()}
                        </div>
                        <Progress
                          value={Math.min(100, Math.round(((usedByAlloc.get(a.id) ?? 0) / a.quota_tokens_per_month) * 100))}
                        />
                      </div>
                    ) : (
                      <div>配額：無上限</div>
                    )
                  )}
                  <div>
                    現價（每 1M）：
                    {a.price
                      ? <span className="font-mono break-words">輸入 ${per1kToPer1m(a.price.input_per_1k)} / 輸出 ${per1kToPer1m(a.price.output_per_1k)}{a.price.cached_input_per_1k && ` / 快取 $${per1kToPer1m(a.price.cached_input_per_1k)}`}</span>
                      : <span>未定價</span>}
                  </div>
                  <div>建立於 {new Date(a.created_at).toLocaleString("zh-TW")}</div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      <Dialog open={!!tokenDialog} onOpenChange={(open) => !open && setTokenDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>憑證已領取 — 此 token 只顯示一次</DialogTitle>
            <DialogDescription>請立即複製並安全保存。關閉後無法再次取得。</DialogDescription>
          </DialogHeader>
          <pre className="bg-muted p-3 rounded text-xs overflow-x-auto break-all">{tokenDialog}</pre>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={async () => {
                if (tokenDialog) await copyToClipboard(tokenDialog);
                toast({ title: "已複製" });
              }}
            >
              複製
            </Button>
            <Button onClick={() => setTokenDialog(null)}>我已複製</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
