import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { CodexLogo } from "@/components/app-logos";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { UsageSummary } from "@/components/usage-summary";
import { useAuth } from "@/contexts/auth";
import { ApiError, api } from "@/lib/api-client";

interface Allocation {
  id: string;
  status: string;
  agent_compatible?: boolean;
}
interface AppCredential {
  id: string;
  status: string;
}
interface ClaimableModel {
  state: "claimable" | "already_claimed" | "reclaim_locked";
}

/**
 * Phase 22: the slim dashboard overview. Summary only — counts + this-month
 * usage + quick install + to-do nudges. Full management lives on 金鑰/分配/用量.
 */
export function MemberOverview() {
  const { member } = useAuth();

  const allocsQuery = useQuery<Allocation[], ApiError>({
    queryKey: ["me", "allocations"],
    queryFn: () => api<Allocation[]>("/me/allocations"),
  });
  const credsQuery = useQuery<AppCredential[], ApiError>({
    queryKey: ["me", "credentials"],
    queryFn: () => api<AppCredential[]>("/me/credentials"),
  });
  const claimableQuery = useQuery<ClaimableModel[], ApiError>({
    queryKey: ["me", "claimable-models"],
    queryFn: () => api<ClaimableModel[]>("/me/claimable-models"),
  });

  const allocs = allocsQuery.data ?? [];
  const activeAllocs = allocs.filter((a) => a.status === "active").length;
  const hasAgentModel = allocs.some((a) => a.status === "active" && a.agent_compatible);
  const activeKeys = (credsQuery.data ?? []).filter((c) => c.status === "active").length;
  const hasNoKey = credsQuery.isSuccess && activeKeys === 0;
  const hasClaimable = (claimableQuery.data ?? []).some((m) => m.state === "claimable");

  return (
    <div className="container mx-auto py-8 space-y-6">
      <section>
        <h1 className="text-3xl font-bold tracking-tight">我的儀表板</h1>
        <p className="text-muted-foreground mt-1">歡迎，{member?.email}</p>
      </section>

      {(hasNoKey || hasClaimable) && (
        <section className="space-y-2">
          {hasNoKey && (
            <Alert>
              <AlertDescription className="flex flex-wrap items-center justify-between gap-2">
                <span>你還沒有任何金鑰。建立一把就能開始呼叫。</span>
                <Link to="/keys" className="font-medium underline underline-offset-4">去建立金鑰 →</Link>
              </AlertDescription>
            </Alert>
          )}
          {hasClaimable && (
            <Alert>
              <AlertDescription className="flex flex-wrap items-center justify-between gap-2">
                <span>有可自助領取的模型等你領取。</span>
                <Link to="/allocations" className="font-medium underline underline-offset-4">去領取 →</Link>
              </AlertDescription>
            </Alert>
          )}
        </section>
      )}

      {/* Phase 34 (049): once you have a key, point to "how to call". */}
      {!hasNoKey && (
        <Alert>
          <AlertDescription className="flex flex-wrap items-center justify-between gap-2">
            <span>有金鑰了？每把金鑰都有「如何使用」——選個模型就有可複製範例。</span>
            <Link to="/keys" className="font-medium underline underline-offset-4">怎麼開始呼叫 →</Link>
          </AlertDescription>
        </Alert>
      )}

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Link to="/keys" className="block">
          <Card className="hover:bg-accent transition-colors cursor-pointer h-full">
            <CardHeader className="pb-2">
              <CardDescription>活躍金鑰</CardDescription>
              <CardTitle className="text-3xl tabular-nums">{activeKeys}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">前往金鑰管理 →</CardContent>
          </Card>
        </Link>
        <Link to="/allocations" className="block">
          <Card className="hover:bg-accent transition-colors cursor-pointer h-full">
            <CardHeader className="pb-2">
              <CardDescription>活躍分配</CardDescription>
              <CardTitle className="text-3xl tabular-nums">{activeAllocs}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">前往分配 →</CardContent>
          </Card>
        </Link>
      </section>

      <section>
        <UsageSummary />
        <div className="mt-2 text-right">
          <Link to="/usage" className="text-sm text-muted-foreground underline underline-offset-4">
            完整用量圖表 →
          </Link>
        </div>
      </section>

      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">應用</h2>
          <Link to="/apps" className="text-sm text-muted-foreground underline underline-offset-4">
            看全部應用 →
          </Link>
        </div>
        {hasAgentModel && (
          <Link to="/apps/codex" className="block">
            <Card className="transition-colors hover:bg-accent">
              <CardContent className="flex items-center gap-3 p-4">
                <div className="shrink-0 rounded-md bg-muted p-2 text-foreground">
                  <CodexLogo className="h-7 w-7" />
                </div>
                <div className="min-w-0">
                  <div className="font-medium">試試 Codex</div>
                  <p className="text-sm text-muted-foreground">
                    你有 Agent 相容的模型——一鍵把 Codex 接上本平台。
                  </p>
                </div>
              </CardContent>
            </Card>
          </Link>
        )}
      </section>
    </div>
  );
}
