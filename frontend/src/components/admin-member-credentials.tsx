import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";
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
 * Phase 21: admin governance of a member's application keys. Read-only list with
 * rename + revoke (no create — keys are the member's). Replaces the old
 * per-allocation "device credentials" dialog (which framed one key under a single
 * model and could silently revoke across its other models).
 */
export function AdminMemberCredentials({ memberId }: { memberId: string }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const key = ["admin", "members", memberId, "credentials"];
  const [renameId, setRenameId] = React.useState<string | null>(null);
  const [renameName, setRenameName] = React.useState("");

  const q = useQuery<AppCredential[], ApiError>({
    queryKey: key,
    queryFn: () => api<AppCredential[]>(`/admin/members/${memberId}/credentials`),
    enabled: !!memberId,
  });
  const invalidate = () => qc.invalidateQueries({ queryKey: key });

  const revokeMut = useMutation({
    mutationFn: (id: string) => api(`/admin/credentials/${id}`, { method: "DELETE" }),
    onSuccess: () => { invalidate(); toast({ title: "已撤回金鑰" }); },
    onError: (e: ApiError) => toast({ title: "撤回失敗", description: e.message, variant: "destructive" }),
  });
  const renameMut = useMutation({
    mutationFn: (v: { id: string; name: string }) =>
      api(`/admin/credentials/${v.id}`, { method: "PATCH", body: JSON.stringify({ name: v.name }) }),
    onSuccess: () => { setRenameId(null); invalidate(); toast({ title: "已改名" }); },
    onError: (e: ApiError) => toast({ title: "改名失敗", description: e.message, variant: "destructive" }),
  });

  const creds = q.data ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">應用金鑰</CardTitle>
        <CardDescription>該成員的應用金鑰；可改名或撤回（撤回會讓該金鑰涵蓋的所有 model 一起失效）。</CardDescription>
      </CardHeader>
      <CardContent>
        {q.isLoading && <p className="text-muted-foreground">載入中…</p>}
        {q.isSuccess && creds.length === 0 && (
          <p className="text-muted-foreground py-3 text-center">此成員還沒有應用金鑰。</p>
        )}
        {creds.length > 0 && (
          <ul className="divide-y">
            {creds.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <div className="min-w-0">
                  {renameId === c.id ? (
                    <div className="flex items-center gap-1">
                      <Input className="h-7 w-40" value={renameName} maxLength={64} onChange={(e) => setRenameName(e.target.value)} />
                      <Button size="sm" className="h-7" disabled={!renameName.trim() || renameMut.isPending} onClick={() => renameMut.mutate({ id: c.id, name: renameName.trim() })}>儲存</Button>
                      <Button size="sm" variant="ghost" className="h-7" onClick={() => setRenameId(null)}>取消</Button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{c.name}</span>
                      <Badge variant={c.status === "active" ? "default" : "secondary"} className="text-[10px]">
                        {c.status === "active" ? "使用中" : "已撤回"}
                      </Badge>
                      <code className="font-mono text-xs text-muted-foreground">{c.token_prefix}…</code>
                    </div>
                  )}
                  <div className="mt-1 flex flex-wrap gap-1">
                    {c.allocations.map((a) => (
                      <Badge key={a.allocation_id} variant="secondary" className="font-mono text-[10px]">
                        {a.display_name ?? a.resource_model}
                      </Badge>
                    ))}
                  </div>
                </div>
                {c.status === "active" && renameId !== c.id && (
                  <div className="flex gap-1">
                    <Button size="sm" variant="ghost" onClick={() => { setRenameId(c.id); setRenameName(c.name); }}>改名</Button>
                    <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive" onClick={() => revokeMut.mutate(c.id)}>撤回</Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
