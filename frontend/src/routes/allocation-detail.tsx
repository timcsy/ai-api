import * as React from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { ApiUsageExample } from "@/components/api-usage-example";
import { per1kToPer1m } from "@/lib/price-format";
import { useToast } from "@/components/ui/use-toast";
import { ApiError, api } from "@/lib/api-client";
import { copyToClipboard } from "@/lib/clipboard";

interface Allocation {
  id: string;
  resource_model: string;
  status: string;
  token_prefix: string;
  quota_tokens_per_month?: number | null;
  price?: { input_per_1k: string; output_per_1k: string; cached_input_per_1k?: string } | null;
}

interface CallItem {
  id: string;
  request_id: string;
  started_at: string;
  finished_at: string;
  status_code: number;
  outcome: string;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
}

interface CallsPage {
  items: CallItem[];
  next_before_id: string | null;
}

export function AllocationDetailPage() {
  const { id = "" } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [rotateConfirmOpen, setRotateConfirmOpen] = React.useState(false);
  const [freshToken, setFreshToken] = React.useState<string | null>(null);

  const rotateMut = useMutation({
    mutationFn: () =>
      api<{ token: string; token_prefix: string }>(
        `/me/allocations/${id}/rotate-token`,
        { method: "POST", headers: { "X-CSRF-Token": document.cookie.match(/aiapi_csrf=([^;]+)/)?.[1] ?? "" } },
      ),
    onSuccess: (data) => {
      setFreshToken(data.token);
      queryClient.invalidateQueries({ queryKey: ["me", "allocations"] });
      queryClient.invalidateQueries({ queryKey: ["me", "allocation-detail", id] });
      toast({ title: "新 token 已產生", description: "舊 token 立即失效" });
    },
    onError: (err: ApiError) => {
      toast({ title: "重新產生失敗", description: err.message, variant: "destructive" });
    },
  });

  const allocQuery = useQuery<Allocation | null, ApiError>({
    // distinct key from the dashboard list ("me","allocations") — sharing it
    // made this read the cached array instead of a single allocation.
    queryKey: ["me", "allocation-detail", id],
    queryFn: async () => {
      const list = await api<Allocation[]>("/me/allocations");
      return list.find((a) => a.id === id) ?? null;
    },
    enabled: !!id,
  });

  // Look up the bound model's catalog entry to know if it supports /responses.
  // Quiet: a missing/forbidden catalog entry just hides the Responses examples.
  const modelSlug = allocQuery.data?.resource_model;
  const modelQuery = useQuery<{ capabilities: string[] }, ApiError>({
    queryKey: ["catalog", "model", modelSlug],
    queryFn: () => api<{ capabilities: string[] }>(`/catalog/models/${modelSlug}`),
    enabled: !!modelSlug,
    retry: false,
  });
  const supportsResponses = !!modelQuery.data?.capabilities?.includes("responses");

  const callsQuery = useInfiniteQuery<CallsPage, ApiError>({
    queryKey: ["me", "allocations", id, "calls"],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => {
      const cursor = pageParam ? `&before_id=${pageParam}` : "";
      return api<CallsPage>(`/me/allocations/${id}/calls?limit=20${cursor}`);
    },
    getNextPageParam: (lastPage) => lastPage.next_before_id,
    enabled: !!id,
  });

  // Error handling: 403 / 404 inline.
  if (callsQuery.error?.status === 403 || allocQuery.error?.status === 403) {
    return (
      <div className="container mx-auto py-10 max-w-md text-center space-y-4">
        <h1 className="text-xl font-semibold">無權限查看</h1>
        <p className="text-muted-foreground">此分配不屬於您的帳號。</p>
        <Button asChild variant="outline">
          <Link to="/dashboard">回首頁</Link>
        </Button>
      </div>
    );
  }
  if (callsQuery.error?.status === 404) {
    return (
      <div className="container mx-auto py-10 max-w-md text-center space-y-4">
        <h1 className="text-xl font-semibold">找不到 allocation</h1>
        <Button asChild variant="outline">
          <Link to="/dashboard">回首頁</Link>
        </Button>
      </div>
    );
  }

  const alloc = allocQuery.data;
  const items = callsQuery.data?.pages.flatMap((p) => p.items) ?? [];
  const usedThisPage = items.reduce((acc, it) => acc + (it.total_tokens ?? 0), 0);
  const quota = alloc?.quota_tokens_per_month ?? null;
  const usagePct = quota ? Math.min(100, Math.round((usedThisPage / quota) * 100)) : 0;
  const isOver = quota !== null && usedThisPage > quota;

  return (
    <div className="container mx-auto py-8 space-y-6">
      <section className="space-y-2">
        <Link to="/dashboard" className="text-sm text-muted-foreground hover:underline">
          ← 回 Dashboard
        </Link>
        <h1 className="text-3xl font-bold">{alloc?.resource_model ?? id}</h1>
        {alloc && (
          <div className="flex items-center gap-2">
            <Badge variant={alloc.status === "active" ? "default" : "secondary"}>
              {alloc.status}
            </Badge>
            <span className="font-mono text-xs text-muted-foreground">
              {alloc.token_prefix}…
            </span>
          </div>
        )}
      </section>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <div>
              <CardTitle className="text-lg">你的憑證</CardTitle>
              <CardDescription>token 僅在建立時顯示一次；系統只存雜湊</CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="shrink-0"
              onClick={() => setRotateConfirmOpen(true)}
              disabled={rotateMut.isPending || alloc?.status !== "active"}
            >
              {rotateMut.isPending ? "產生中…" : "重新產生 token"}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-xs text-muted-foreground mb-1">Token 前綴</div>
          <code className="text-sm bg-muted px-2 py-1 rounded font-mono">{alloc?.token_prefix}…</code>
        </CardContent>
      </Card>

      <ApiUsageExample model={alloc?.resource_model ?? ""} supportsResponses={supportsResponses} />

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">配額與價格</CardTitle>
          <CardDescription>
            {quota === null
              ? "配額：無限額"
              : `配額：已用 ${usedThisPage.toLocaleString()} / ${quota.toLocaleString()}`}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {quota !== null && (
            <>
              <Progress value={usagePct} className={isOver ? "[&>div]:bg-destructive" : ""} />
              {isOver && <p className="text-destructive text-sm">⚠ 超出本月配額</p>}
            </>
          )}
          <div className="text-sm">
            <span className="text-muted-foreground">價格（每 1M tokens）：</span>
            {alloc?.price
              ? <span className="font-mono">輸入 ${per1kToPer1m(alloc.price.input_per_1k)} / 輸出 ${per1kToPer1m(alloc.price.output_per_1k)}{alloc.price.cached_input_per_1k && ` / 快取輸入 $${per1kToPer1m(alloc.price.cached_input_per_1k)}`}</span>
              : <span className="text-muted-foreground">未定價</span>}
            {alloc && (
              <Link to={`/catalog/${alloc.resource_model}`} className="ml-2 text-xs text-primary hover:underline">
                看模型詳情 →
              </Link>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">最近呼叫</CardTitle>
        </CardHeader>
        <CardContent>
          {callsQuery.isLoading && <p className="text-muted-foreground">載入中…</p>}
          {callsQuery.error && !callsQuery.error.status && (
            <Alert variant="destructive">
              <AlertDescription>無法載入呼叫紀錄</AlertDescription>
            </Alert>
          )}
          {items.length === 0 && callsQuery.isSuccess && (
            <p className="text-muted-foreground py-6 text-center">尚無呼叫紀錄</p>
          )}
          {items.length > 0 && (
            <div className="space-y-2">
              <div className="grid grid-cols-[1.6fr_0.6fr_1fr_0.8fr_1.4fr] gap-3 text-xs font-medium text-muted-foreground border-b pb-2">
                <span>時間</span>
                <span>狀態</span>
                <span>結果</span>
                <span className="text-right">總 tokens</span>
                <span className="text-right">請求 ID</span>
              </div>
              {items.map((c) => (
                <div key={c.id} className="grid grid-cols-[1.6fr_0.6fr_1fr_0.8fr_1.4fr] gap-3 text-sm py-1 border-b border-border/30">
                  <span className="truncate">{new Date(c.started_at).toLocaleString("zh-TW")}</span>
                  <span>{c.status_code}</span>
                  <span className="text-xs truncate">{c.outcome}</span>
                  <span className="text-right tabular-nums">{c.total_tokens ?? "—"}</span>
                  <span className="min-w-0 text-right font-mono text-xs text-muted-foreground truncate" title={c.request_id}>
                    {c.request_id}
                  </span>
                </div>
              ))}
              {callsQuery.hasNextPage && (
                <div className="pt-3 text-center">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={callsQuery.isFetchingNextPage}
                    onClick={() => void callsQuery.fetchNextPage()}
                  >
                    {callsQuery.isFetchingNextPage ? "載入中…" : "載入更多"}
                  </Button>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <AlertDialog open={rotateConfirmOpen} onOpenChange={setRotateConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>確認重新產生 token？</AlertDialogTitle>
            <AlertDialogDescription>
              產生新 token 後，舊 token <strong>立即失效</strong>。請確保已準備好更新所有使用此 token 的程式 / 腳本。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setRotateConfirmOpen(false);
                rotateMut.mutate();
              }}
            >
              確認重新產生
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={!!freshToken} onOpenChange={(open) => !open && setFreshToken(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新 token — 此次顯示後無法再取得</DialogTitle>
            <DialogDescription>
              請立即複製並安全保存。關閉後系統僅保留雜湊。
            </DialogDescription>
          </DialogHeader>
          <pre className="bg-muted p-3 rounded text-xs overflow-x-auto break-all">
            {freshToken}
          </pre>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={async () => {
                if (freshToken) await copyToClipboard(freshToken);
                toast({ title: "已複製" });
              }}
            >
              複製
            </Button>
            <Button onClick={() => setFreshToken(null)}>我已複製</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
