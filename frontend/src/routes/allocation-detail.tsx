import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { ApiError, api } from "@/lib/api-client";

interface Allocation {
  id: string;
  resource_model: string;
  status: string;
  token_prefix: string;
  quota_tokens_per_month?: number | null;
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

  const allocQuery = useQuery<Allocation | null, ApiError>({
    queryKey: ["me", "allocations"],
    queryFn: async () => {
      const list = await api<Allocation[]>("/me/allocations");
      return list.find((a) => a.id === id) ?? null;
    },
    enabled: !!id,
  });

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
          <CardTitle className="text-lg">配額</CardTitle>
          <CardDescription>
            {quota === null
              ? "無限額"
              : `已用 ${usedThisPage.toLocaleString()} / ${quota.toLocaleString()}`}
          </CardDescription>
        </CardHeader>
        {quota !== null && (
          <CardContent>
            <Progress value={usagePct} className={isOver ? "[&>div]:bg-destructive" : ""} />
            {isOver && (
              <p className="text-destructive text-sm mt-2">⚠ 超出本月配額</p>
            )}
          </CardContent>
        )}
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
              <div className="grid grid-cols-5 text-xs font-medium text-muted-foreground border-b pb-2">
                <span>時間</span>
                <span>狀態</span>
                <span>結果</span>
                <span className="text-right">tokens</span>
                <span className="text-right">request_id</span>
              </div>
              {items.map((c) => (
                <div key={c.id} className="grid grid-cols-5 text-sm py-1 border-b border-border/30">
                  <span>{new Date(c.started_at).toLocaleString("zh-TW")}</span>
                  <span>{c.status_code}</span>
                  <span className="text-xs">{c.outcome}</span>
                  <span className="text-right">{c.total_tokens ?? "—"}</span>
                  <span className="text-right font-mono text-xs text-muted-foreground truncate">
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
    </div>
  );
}
