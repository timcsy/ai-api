import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/contexts/auth";
import { ApiError, api } from "@/lib/api-client";

interface Allocation {
  id: string;
  member_id: string;
  subject_snapshot: string;
  resource_model: string;
  status: string;
  created_at: string;
  revoked_at: string | null;
  token_prefix: string;
}

export function DashboardPage() {
  const { member } = useAuth();
  const [includeRevoked, setIncludeRevoked] = React.useState(false);

  const query = useQuery<Allocation[], ApiError>({
    queryKey: ["me", "allocations"],
    queryFn: () => api<Allocation[]>("/me/allocations"),
  });

  const filtered = React.useMemo(() => {
    if (!query.data) return [];
    return includeRevoked
      ? query.data
      : query.data.filter((a) => a.status === "active");
  }, [query.data, includeRevoked]);

  return (
    <div className="container mx-auto py-8 space-y-6">
      <section>
        <h1 className="text-3xl font-bold tracking-tight">我的儀表板</h1>
        <p className="text-muted-foreground mt-1">歡迎，{member?.email}</p>
        <div className="mt-2 flex gap-2 text-sm text-muted-foreground">
          <span>登入方式：{member?.provider}</span>
          {query.data && <span>· 啟用中分配：{filtered.length}</span>}
        </div>
        <Card className="mt-4">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">API 端點</CardTitle>
            <CardDescription>
              呼叫時將 token 放於 <code className="text-xs">Authorization: Bearer</code> 標頭
            </CardDescription>
          </CardHeader>
          <CardContent>
            <code className="text-sm bg-muted px-2 py-1 rounded">
              {window.location.origin}/v1
            </code>
            {member?.gateway_base_url &&
              !window.location.origin.startsWith(member.gateway_base_url) && (
              <p className="text-xs text-muted-foreground mt-2">
                如果你從其他主機呼叫，可改用 admin 設定的 base URL：
                <code className="ml-1">{member.gateway_base_url}/v1</code>
              </p>
            )}
          </CardContent>
        </Card>
        <Alert className="mt-3">
          <AlertDescription>
            您的 API token 在管理員建立分配時一次性顯示；系統僅保存雜湊。如需取得新 token，
            請進入單筆分配後點「重新產生 token」（舊 token 立即失效）。
          </AlertDescription>
        </Alert>
      </section>

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
            <CardContent className="py-10 text-center text-muted-foreground">
              尚未獲得任何分配，請聯絡管理員。
            </CardContent>
          </Card>
        )}

        <div className="grid gap-4 md:grid-cols-2">
          {filtered.map((a) => (
            <Link key={a.id} to={`/dashboard/allocations/${a.id}`}>
              <Card className="hover:bg-accent transition-colors cursor-pointer">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{a.resource_model}</CardTitle>
                    <Badge variant={a.status === "active" ? "default" : "secondary"}>
                      {a.status}
                    </Badge>
                  </div>
                  <CardDescription className="font-mono text-xs">
                    {a.token_prefix}…
                  </CardDescription>
                </CardHeader>
                <CardContent className="text-xs text-muted-foreground">
                  建立於 {new Date(a.created_at).toLocaleString("zh-TW")}
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
