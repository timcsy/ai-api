import * as React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/components/ui/use-toast";
import { ApiError, api } from "@/lib/api-client";

interface DeviceRequest {
  user_code: string;
  device_label: string | null;
  status: string;
  created_at: string;
  expires_at: string;
}

interface Allocation {
  id: string;
  resource_model: string;
  display_name?: string | null;
  status: string;
}

/**
 * Phase 19 device-flow authorization page (`/device`). The Codex install script
 * shows the member a `user_code`; here (already logged in) they confirm it, pick
 * which allocation this device should use, and approve — which mints a per-device
 * credential the script then fetches. No token is ever copy-pasted.
 */
export function DeviceAuthorizePage() {
  const [params] = useSearchParams();
  const { toast } = useToast();
  const [code, setCode] = React.useState(params.get("code") ?? "");
  const [submittedCode, setSubmittedCode] = React.useState(params.get("code") ?? "");
  const [pick, setPick] = React.useState<Set<string>>(new Set());
  const [done, setDone] = React.useState<"approved" | "denied" | null>(null);

  const reqQuery = useQuery<DeviceRequest, ApiError>({
    queryKey: ["me", "device", submittedCode],
    queryFn: () => api<DeviceRequest>(`/me/device/${encodeURIComponent(submittedCode)}`),
    enabled: !!submittedCode,
    retry: false,
  });

  const allocsQuery = useQuery<Allocation[], ApiError>({
    queryKey: ["me", "allocations"],
    queryFn: () => api<Allocation[]>("/me/allocations"),
    enabled: !!submittedCode,
  });
  const activeAllocs = (allocsQuery.data ?? []).filter((a) => a.status === "active");

  const approveMut = useMutation({
    mutationFn: () =>
      api(`/me/device/${encodeURIComponent(submittedCode)}/approve`, {
        method: "POST",
        body: JSON.stringify({ allocation_ids: [...pick] }),
      }),
    onSuccess: () => {
      setDone("approved");
      toast({ title: "已授權", description: "請回到終端機，安裝會自動完成" });
    },
    onError: (err: ApiError) =>
      toast({ title: "授權失敗", description: err.message, variant: "destructive" }),
  });

  const denyMut = useMutation({
    mutationFn: () =>
      api(`/me/device/${encodeURIComponent(submittedCode)}/deny`, { method: "POST" }),
    onSuccess: () => {
      setDone("denied");
      toast({ title: "已拒絕此裝置授權" });
    },
    onError: (err: ApiError) =>
      toast({ title: "操作失敗", description: err.message, variant: "destructive" }),
  });

  return (
    <div className="container mx-auto max-w-md py-10">
      <Card>
        <CardHeader>
          <CardTitle>授權裝置安裝 Codex</CardTitle>
          <CardDescription>
            確認終端機顯示的代碼，選擇要讓這台裝置使用的分配，再按授權。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {done === "approved" && (
            <Alert>
              <AlertDescription>✓ 已授權，請回到終端機，安裝會自動完成。</AlertDescription>
            </Alert>
          )}
          {done === "denied" && (
            <Alert variant="destructive">
              <AlertDescription>已拒絕此裝置授權。</AlertDescription>
            </Alert>
          )}

          {!done && (
            <>
              <div className="space-y-2">
                <Label htmlFor="user-code">裝置代碼</Label>
                <div className="flex gap-2">
                  <Input
                    id="user-code"
                    value={code}
                    placeholder="ABCD-EFGH"
                    autoCapitalize="characters"
                    onChange={(e) => setCode(e.target.value.toUpperCase())}
                  />
                  <Button variant="outline" onClick={() => setSubmittedCode(code.trim())}>
                    查詢
                  </Button>
                </div>
              </div>

              {reqQuery.error && (
                <Alert variant="destructive">
                  <AlertDescription>找不到或已過期的代碼，請回終端機重跑安裝指令。</AlertDescription>
                </Alert>
              )}

              {reqQuery.data && (
                <div className="space-y-4">
                  <div className="text-sm text-muted-foreground">
                    裝置：<span className="text-foreground">{reqQuery.data.device_label ?? "未命名裝置"}</span>
                  </div>
                  <div className="space-y-2">
                    <Label>這台裝置可用哪些 model（可多選）</Label>
                    <div className="max-h-48 space-y-1 overflow-y-auto rounded-md border p-2">
                      {activeAllocs.map((a) => (
                        <label key={a.id} className="flex items-center gap-2 py-1 text-sm">
                          <Checkbox
                            checked={pick.has(a.id)}
                            onCheckedChange={(v) =>
                              setPick((s) => {
                                const n = new Set(s);
                                if (v) n.add(a.id);
                                else n.delete(a.id);
                                return n;
                              })
                            }
                          />
                          <span className="font-mono text-xs">{a.display_name ?? a.resource_model}</span>
                        </label>
                      ))}
                    </div>
                    {activeAllocs.length === 0 && allocsQuery.isSuccess && (
                      <p className="text-xs text-muted-foreground">
                        你還沒有可用的分配，請先到 Dashboard 領取一個 model。
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      className="flex-1"
                      disabled={pick.size === 0 || approveMut.isPending}
                      onClick={() => approveMut.mutate()}
                    >
                      {approveMut.isPending ? "授權中…" : "授權這台裝置"}
                    </Button>
                    <Button variant="outline" onClick={() => denyMut.mutate()}>
                      拒絕
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
