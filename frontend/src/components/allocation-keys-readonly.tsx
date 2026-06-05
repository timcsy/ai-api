import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, api } from "@/lib/api-client";

interface AllocationRef {
  allocation_id: string;
  resource_model: string;
  display_name: string | null;
  status: string;
}
interface AppCredential {
  id: string;
  name: string;
  token_prefix: string;
  status: string;
  allocations: AllocationRef[];
}

/**
 * Phase 21: read-only "which application keys can use THIS model" on the
 * allocation-detail page. Each key shows its FULL set of models (so the user
 * sees that revoking it would affect those too) and links to the single
 * management surface (dashboard). No revoke / add / rotate here — that lives
 * with the key itself, where the full scope is visible (no silent collateral).
 */
export function AllocationKeysReadonly({ allocationId }: { allocationId: string }) {
  const q = useQuery<AppCredential[], ApiError>({
    queryKey: ["me", "credentials"],
    queryFn: () => api<AppCredential[]>("/me/credentials"),
  });
  const keys = (q.data ?? []).filter((k) =>
    k.allocations.some((a) => a.allocation_id === allocationId),
  );

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="text-lg">能用這個 model 的應用金鑰</CardTitle>
            <CardDescription>
              金鑰可同時涵蓋多個 model；建立 / 改名 / 撤回請到「我的應用金鑰」統一管理。
            </CardDescription>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link to="/dashboard">前往管理</Link>
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {q.isLoading && <p className="text-muted-foreground">載入中…</p>}
        {q.isSuccess && keys.length === 0 && (
          <p className="text-muted-foreground py-4 text-center">
            還沒有能用這個 model 的應用金鑰——到「我的應用金鑰」建立一把並勾選它。
          </p>
        )}
        {keys.length > 0 && (
          <ul className="divide-y">
            {keys.map((k) => (
              <li key={k.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{k.name}</span>
                    <Badge variant={k.status === "active" ? "default" : "secondary"} className="text-[10px]">
                      {k.status === "active" ? "使用中" : "已撤回"}
                    </Badge>
                    <code className="font-mono text-xs text-muted-foreground">{k.token_prefix}…</code>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {k.allocations.map((a) => (
                      <Badge
                        key={a.allocation_id}
                        variant={a.allocation_id === allocationId ? "default" : "secondary"}
                        className="font-mono text-[10px]"
                      >
                        {a.display_name ?? a.resource_model}
                      </Badge>
                    ))}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
