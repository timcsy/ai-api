import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { copyToClipboard } from "@/lib/clipboard";

export interface DeviceCredential {
  id: string;
  name: string;
  token_prefix: string;
  created_at: string;
  last_used_at: string | null;
  status: string; // "active" | "revoked"
}

interface CreatedCredential {
  id: string;
  name: string;
  token: string;
  token_prefix: string;
}

interface Props {
  /** Allocation whose credentials are shown. */
  allocationId: string;
  /** API prefix: "/me/allocations" (member) or "/admin/allocations" (admin). */
  basePath: string;
  /** Query-key scope so member vs admin caches don't collide. */
  scope: "me" | "admin";
  /** Whether the current viewer may add new device credentials (member only). */
  allowAdd?: boolean;
  /** Gate the query — used to lazy-load inside an admin dialog. */
  enabled?: boolean;
}

function fmt(ts: string | null): string {
  return ts ? new Date(ts).toLocaleString("zh-TW") : "—";
}

/**
 * Per-device credential list + add/revoke. Phase 18: one allocation can carry
 * many independent named credentials (one per device). Plaintext is shown ONCE
 * on creation; the platform only stores the hash.
 */
export function DeviceCredentialsCard({
  allocationId,
  basePath,
  scope,
  allowAdd = false,
  enabled = true,
}: Props) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const queryKey = [scope, "credentials", allocationId];

  const [addOpen, setAddOpen] = React.useState(false);
  const [newName, setNewName] = React.useState("");
  const [freshToken, setFreshToken] = React.useState<CreatedCredential | null>(null);
  const [revokeTarget, setRevokeTarget] = React.useState<DeviceCredential | null>(null);

  const credsQuery = useQuery<DeviceCredential[], ApiError>({
    queryKey,
    queryFn: () => api<DeviceCredential[]>(`${basePath}/${allocationId}/credentials`),
    enabled: enabled && !!allocationId,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey });

  const addMut = useMutation({
    mutationFn: (name: string) =>
      api<CreatedCredential>(`${basePath}/${allocationId}/credentials`, {
        method: "POST",
        body: JSON.stringify({ name }),
      }),
    onSuccess: (data) => {
      setAddOpen(false);
      setNewName("");
      setFreshToken(data);
      invalidate();
      toast({ title: "已新增裝置憑證", description: "請立即複製 token，僅顯示一次" });
    },
    onError: (err: ApiError) => {
      toast({ title: "新增失敗", description: err.message, variant: "destructive" });
    },
  });

  const revokeMut = useMutation({
    mutationFn: (credId: string) =>
      api(`${basePath}/${allocationId}/credentials/${credId}`, { method: "DELETE" }),
    onSuccess: () => {
      setRevokeTarget(null);
      invalidate();
      toast({ title: "已撤回該裝置憑證", description: "其他裝置不受影響" });
    },
    onError: (err: ApiError) => {
      toast({ title: "撤回失敗", description: err.message, variant: "destructive" });
    },
  });

  const rotateMut = useMutation({
    mutationFn: (credId: string) =>
      api<CreatedCredential>(`${basePath}/${allocationId}/credentials/${credId}/rotate`, {
        method: "POST",
      }),
    onSuccess: (data) => {
      setFreshToken(data);
      invalidate();
      toast({ title: "已重新產生 token", description: "舊 token 立即失效，請複製新的" });
    },
    onError: (err: ApiError) => {
      toast({ title: "重新產生失敗", description: err.message, variant: "destructive" });
    },
  });

  const creds = credsQuery.data ?? [];

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="text-lg">裝置與憑證</CardTitle>
            <CardDescription>
              每台裝置一把獨立 token；撤回單把不影響其他。token 僅在新增時顯示一次。
            </CardDescription>
          </div>
          {allowAdd && (
            <Button size="sm" onClick={() => setAddOpen(true)}>
              新增裝置
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {credsQuery.isLoading && <p className="text-muted-foreground">載入中…</p>}
        {credsQuery.isSuccess && creds.length === 0 && (
          <p className="text-muted-foreground py-4 text-center">尚無憑證</p>
        )}
        {creds.length > 0 && (
          <Table className="responsive-table">
            <TableHeader>
              <TableRow>
                <TableHead>裝置名</TableHead>
                <TableHead>Token 前綴</TableHead>
                <TableHead>建立</TableHead>
                <TableHead>最後使用</TableHead>
                <TableHead>狀態</TableHead>
                {(allowAdd || scope === "admin") && (
                  <TableHead className="text-right">操作</TableHead>
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {creds.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="font-medium" data-label="裝置名">
                    {c.name}
                  </TableCell>
                  <TableCell className="font-mono text-xs" data-label="Token 前綴">
                    {c.token_prefix}…
                  </TableCell>
                  <TableCell className="text-xs" data-label="建立">
                    {fmt(c.created_at)}
                  </TableCell>
                  <TableCell className="text-xs" data-label="最後使用">
                    {fmt(c.last_used_at)}
                  </TableCell>
                  <TableCell data-label="狀態">
                    <Badge variant={c.status === "active" ? "default" : "secondary"}>
                      {c.status === "active" ? "使用中" : "已撤回"}
                    </Badge>
                  </TableCell>
                  {(allowAdd || scope === "admin") && (
                    <TableCell className="text-right" data-label="操作">
                      {c.status === "active" ? (
                        <div className="flex justify-end gap-1">
                          {allowAdd && (
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={rotateMut.isPending}
                              onClick={() => rotateMut.mutate(c.id)}
                            >
                              重新產生
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:text-destructive"
                            onClick={() => setRevokeTarget(c)}
                          >
                            撤回
                          </Button>
                        </div>
                      ) : (
                        <span className="text-muted-foreground text-xs">—</span>
                      )}
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      {/* Add-device dialog */}
      <Dialog open={addOpen} onOpenChange={(o) => !o && setAddOpen(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新增裝置憑證</DialogTitle>
            <DialogDescription>
              為這台裝置取一個好記的名字（例如「我的筆電」）。新增後會顯示一次 token。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="device-name">裝置名</Label>
            <Input
              id="device-name"
              value={newName}
              maxLength={64}
              placeholder="我的筆電"
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && newName.trim()) addMut.mutate(newName.trim());
              }}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)}>
              取消
            </Button>
            <Button
              disabled={!newName.trim() || addMut.isPending}
              onClick={() => addMut.mutate(newName.trim())}
            >
              {addMut.isPending ? "新增中…" : "新增"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reveal-once token dialog */}
      <Dialog open={!!freshToken} onOpenChange={(o) => !o && setFreshToken(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>「{freshToken?.name}」的 token — 僅顯示這一次</DialogTitle>
            <DialogDescription>
              請立即複製並貼到該裝置。關閉後系統僅保留雜湊，無法再次取得。
            </DialogDescription>
          </DialogHeader>
          <pre className="bg-muted p-3 rounded text-xs overflow-x-auto break-all">
            {freshToken?.token}
          </pre>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={async () => {
                if (freshToken) await copyToClipboard(freshToken.token);
                toast({ title: "已複製" });
              }}
            >
              複製
            </Button>
            <Button onClick={() => setFreshToken(null)}>我已複製</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Revoke confirm */}
      <AlertDialog open={!!revokeTarget} onOpenChange={(o) => !o && setRevokeTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>撤回「{revokeTarget?.name}」？</AlertDialogTitle>
            <AlertDialogDescription>
              此裝置的 token 將<strong>立即失效</strong>，且無法復原。同一分配的其他裝置不受影響。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => revokeTarget && revokeMut.mutate(revokeTarget.id)}
            >
              確認撤回
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
