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
import { Checkbox } from "@/components/ui/checkbox";
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
import { Switch } from "@/components/ui/switch";
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
  created_at: string;
  last_used_at: string | null;
  status: string;
  allocations: AllocationRef[];
}
interface Created {
  id: string;
  name: string;
  token: string;
  token_prefix: string;
  allocations: AllocationRef[];
}
interface Allocation {
  id: string;
  resource_model: string;
  display_name?: string | null;
  status: string;
}

function fmt(ts: string | null): string {
  return ts ? new Date(ts).toLocaleString("zh-TW") : "—";
}

/**
 * Phase 20: member-level "我的應用 / 金鑰". A credential is an application key
 * scoped to a SET of the member's allocations (models); one key can call all of
 * them. Create with a multi-select; edit scope, rotate, revoke per key.
 */
export function AppCredentialsCard() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const key = ["me", "credentials"];

  const credsQuery = useQuery<AppCredential[], ApiError>({
    queryKey: key,
    queryFn: () => api<AppCredential[]>("/me/credentials"),
  });
  const allocsQuery = useQuery<Allocation[], ApiError>({
    queryKey: ["me", "allocations"],
    queryFn: () => api<Allocation[]>("/me/allocations"),
  });
  const activeAllocs = (allocsQuery.data ?? []).filter((a) => a.status === "active");

  const [createOpen, setCreateOpen] = React.useState(false);
  const [newName, setNewName] = React.useState("");
  const [pick, setPick] = React.useState<Set<string>>(new Set());
  const [fresh, setFresh] = React.useState<Created | null>(null);
  const [revokeTarget, setRevokeTarget] = React.useState<AppCredential | null>(null);
  const [editTarget, setEditTarget] = React.useState<AppCredential | null>(null);
  const [editPick, setEditPick] = React.useState<Set<string>>(new Set());
  const [editName, setEditName] = React.useState("");
  const [showRevoked, setShowRevoked] = React.useState(false);

  const invalidate = () => qc.invalidateQueries({ queryKey: key });

  const createMut = useMutation({
    mutationFn: () =>
      api<Created>("/me/credentials", {
        method: "POST",
        body: JSON.stringify({ name: newName.trim(), allocation_ids: [...pick] }),
      }),
    onSuccess: (d) => {
      setCreateOpen(false);
      setNewName("");
      setPick(new Set());
      setFresh(d);
      invalidate();
      toast({ title: "已建立應用金鑰", description: "請立即複製 token，僅顯示一次" });
    },
    onError: (e: ApiError) => toast({ title: "建立失敗", description: e.message, variant: "destructive" }),
  });

  const revokeMut = useMutation({
    mutationFn: (id: string) => api(`/me/credentials/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setRevokeTarget(null);
      invalidate();
      toast({ title: "已撤回金鑰", description: "其涵蓋的模型全部失效，其他金鑰不受影響" });
    },
    onError: (e: ApiError) => toast({ title: "撤回失敗", description: e.message, variant: "destructive" }),
  });

  const rotateMut = useMutation({
    mutationFn: (id: string) => api<Created>(`/me/credentials/${id}/rotate`, { method: "POST" }),
    onSuccess: (d) => {
      setFresh(d);
      invalidate();
      toast({ title: "已重新產生 token", description: "舊 token 立即失效" });
    },
    onError: (e: ApiError) => toast({ title: "重新產生失敗", description: e.message, variant: "destructive" }),
  });

  // Phase 22: a single "編輯" sends name + scope diff together. The backend
  // PATCH accepts name/add/remove in one call (see test_credential_rename.py).
  const patchMut = useMutation({
    mutationFn: (v: { id: string; body: Record<string, unknown> }) =>
      api(`/me/credentials/${v.id}`, { method: "PATCH", body: JSON.stringify(v.body) }),
    onSuccess: () => {
      setEditTarget(null);
      invalidate();
      toast({ title: "已更新金鑰" });
    },
    onError: (e: ApiError) => toast({ title: "更新失敗", description: e.message, variant: "destructive" }),
  });

  function openEdit(c: AppCredential) {
    setEditTarget(c);
    setEditName(c.name);
    setEditPick(new Set(c.allocations.map((a) => a.allocation_id)));
  }
  function applyEdit() {
    if (!editTarget) return;
    const before = new Set(editTarget.allocations.map((a) => a.allocation_id));
    const add = [...editPick].filter((id) => !before.has(id));
    const remove = [...before].filter((id) => !editPick.has(id));
    const body: Record<string, unknown> = {};
    const trimmed = editName.trim();
    if (trimmed && trimmed !== editTarget.name) body.name = trimmed;
    if (add.length) body.add = add;
    if (remove.length) body.remove = remove;
    if (Object.keys(body).length === 0) {
      setEditTarget(null);
      return;
    }
    patchMut.mutate({ id: editTarget.id, body });
  }

  const allCreds = credsQuery.data ?? [];
  const revokedCount = allCreds.filter((c) => c.status !== "active").length;
  const creds = showRevoked ? allCreds : allCreds.filter((c) => c.status === "active");

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="text-lg">我的應用 / 金鑰</CardTitle>
            <CardDescription>
              一把金鑰可指定多個模型（分配）；同一把 token 即可呼叫全部。token 僅在建立時顯示一次。
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {revokedCount > 0 && (
              <div className="flex items-center gap-2">
                <Switch id="show-revoked-keys" checked={showRevoked} onCheckedChange={setShowRevoked} />
                <Label htmlFor="show-revoked-keys" className="text-sm">含已撤回</Label>
              </div>
            )}
            <Button size="sm" onClick={() => setCreateOpen(true)} disabled={activeAllocs.length === 0}>
              建立金鑰
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {credsQuery.isLoading && <p className="text-muted-foreground">載入中…</p>}
        {credsQuery.isSuccess && allCreds.length === 0 && (
          <p className="text-muted-foreground py-4 text-center">尚無應用金鑰</p>
        )}
        {credsQuery.isSuccess && allCreds.length > 0 && creds.length === 0 && (
          <p className="text-muted-foreground py-4 text-center">沒有使用中的金鑰（{revokedCount} 把已撤回）</p>
        )}
        {creds.length > 0 && (
          <Table className="responsive-table">
            <TableHeader>
              <TableRow>
                <TableHead>名稱</TableHead>
                <TableHead>可用模型</TableHead>
                <TableHead>Token 前綴</TableHead>
                <TableHead>最後使用</TableHead>
                <TableHead>狀態</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {creds.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="font-medium" data-label="名稱">{c.name}</TableCell>
                  <TableCell data-label="可用模型">
                    <div className="flex flex-wrap gap-1">
                      {c.allocations.map((a) => (
                        <Badge key={a.allocation_id} variant="secondary" className="font-mono text-[10px]">
                          {a.display_name ?? a.resource_model}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="font-mono text-xs" data-label="Token 前綴">{c.token_prefix}…</TableCell>
                  <TableCell className="text-xs" data-label="最後使用">{fmt(c.last_used_at)}</TableCell>
                  <TableCell data-label="狀態">
                    <Badge variant={c.status === "active" ? "default" : "secondary"}>
                      {c.status === "active" ? "使用中" : "已撤回"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right" data-label="操作">
                    {c.status === "active" ? (
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => openEdit(c)}>編輯</Button>
                        <Button variant="ghost" size="sm" disabled={rotateMut.isPending} onClick={() => rotateMut.mutate(c.id)}>重新產生</Button>
                        <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => setRevokeTarget(c)}>撤回</Button>
                      </div>
                    ) : (
                      <span className="text-muted-foreground text-xs">—</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      {/* Create */}
      <Dialog open={createOpen} onOpenChange={(o) => !o && setCreateOpen(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>建立應用金鑰</DialogTitle>
            <DialogDescription>取個名字，勾選這把金鑰可用的模型。</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="key-name">名稱</Label>
              <Input id="key-name" value={newName} maxLength={64} placeholder="我的筆電 Codex" onChange={(e) => setNewName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>可用模型</Label>
              <div className="max-h-48 space-y-1 overflow-y-auto rounded-md border p-2">
                {activeAllocs.map((a) => (
                  <label key={a.id} className="flex items-center gap-2 py-1 text-sm">
                    <Checkbox
                      checked={pick.has(a.id)}
                      onCheckedChange={(v) =>
                        setPick((s) => {
                          const n = new Set(s);
                          if (v) n.add(a.id); else n.delete(a.id);
                          return n;
                        })
                      }
                    />
                    <span className="font-mono text-xs">{a.display_name ?? a.resource_model}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>取消</Button>
            <Button disabled={!newName.trim() || pick.size === 0 || createMut.isPending} onClick={() => createMut.mutate()}>
              {createMut.isPending ? "建立中…" : "建立"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit (name + scope together) */}
      <Dialog open={!!editTarget} onOpenChange={(o) => !o && setEditTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>編輯金鑰</DialogTitle>
            <DialogDescription>改名稱與可用模型都在這裡，按儲存一次生效（同一把 token，不需換）。至少保留一個模型。</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="edit-name">名稱</Label>
              <Input
                id="edit-name"
                value={editName}
                maxLength={64}
                onChange={(e) => setEditName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>可用模型</Label>
              <div className="max-h-56 space-y-1 overflow-y-auto rounded-md border p-2">
                {activeAllocs.map((a) => (
                  <label key={a.id} className="flex items-center gap-2 py-1 text-sm">
                    <Checkbox
                      checked={editPick.has(a.id)}
                      onCheckedChange={(v) =>
                        setEditPick((s) => {
                          const n = new Set(s);
                          if (v) n.add(a.id); else n.delete(a.id);
                          return n;
                        })
                      }
                    />
                    <span className="font-mono text-xs">{a.display_name ?? a.resource_model}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditTarget(null)}>取消</Button>
            <Button disabled={!editName.trim() || editPick.size === 0 || patchMut.isPending} onClick={applyEdit}>
              {patchMut.isPending ? "儲存中…" : "儲存"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reveal-once token */}
      <Dialog open={!!fresh} onOpenChange={(o) => !o && setFresh(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>「{fresh?.name}」的 token — 僅顯示這一次</DialogTitle>
            <DialogDescription>請立即複製。關閉後系統僅保留雜湊，無法再次取得。</DialogDescription>
          </DialogHeader>
          <pre className="bg-muted p-3 rounded text-xs overflow-x-auto break-all">{fresh?.token}</pre>
          <DialogFooter>
            <Button variant="outline" onClick={async () => { if (fresh) await copyToClipboard(fresh.token); toast({ title: "已複製" }); }}>複製</Button>
            <Button onClick={() => setFresh(null)}>我已複製</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Revoke confirm */}
      <AlertDialog open={!!revokeTarget} onOpenChange={(o) => !o && setRevokeTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>撤回「{revokeTarget?.name}」？</AlertDialogTitle>
            <AlertDialogDescription>
              這把金鑰涵蓋的{" "}
              <strong>
                {revokeTarget?.allocations.length ?? 0} 個模型（
                {revokeTarget?.allocations.map((a) => a.display_name ?? a.resource_model).join("、")}）會一起立即失效
              </strong>
              、無法復原。其他金鑰不受影響。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction className="bg-destructive text-destructive-foreground hover:bg-destructive/90" onClick={() => revokeTarget && revokeMut.mutate(revokeTarget.id)}>
              確認撤回
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
