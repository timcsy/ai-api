import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { CodexInstallCard } from "@/components/codex-install-card";
import {
  AlertDialog,
  AlertDialogAction,
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
import { useToast } from "@/components/ui/use-toast";
import { useAuth } from "@/contexts/auth";
import { ApiError, api } from "@/lib/api-client";
import { copyToClipboard } from "@/lib/clipboard";

interface Allocation {
  id: string;
  resource_model: string;
  display_name: string | null;
  status: string;
  agent_compatible?: boolean;
}
interface Created {
  id: string;
  name: string;
  token: string;
  token_prefix: string;
}

/**
 * Phase 27: 應用目錄 — connect your platform key to real client apps.
 * v1 ships a single Codex card; more OpenAI-compatible apps slot in as cards later.
 */
export function ApplicationsPage() {
  const { member } = useAuth();
  const { toast } = useToast();
  const qc = useQueryClient();
  const baseUrl = member?.gateway_base_url ?? window.location.origin;

  const allocsQuery = useQuery<Allocation[], ApiError>({
    queryKey: ["me", "allocations"],
    queryFn: () => api<Allocation[]>("/me/allocations"),
  });
  const agentAllocs = (allocsQuery.data ?? []).filter(
    (a) => a.status === "active" && a.agent_compatible,
  );

  const [createOpen, setCreateOpen] = React.useState(false);
  const [name, setName] = React.useState("Codex");
  const [pick, setPick] = React.useState<Set<string>>(new Set());
  const [fresh, setFresh] = React.useState<Created | null>(null);

  const openCreate = () => {
    setName("Codex");
    setPick(new Set(agentAllocs.map((a) => a.id))); // pre-select all agent-compatible
    setCreateOpen(true);
  };

  const createMut = useMutation<Created, ApiError, void>({
    mutationFn: () =>
      api<Created>("/me/credentials", {
        method: "POST",
        body: JSON.stringify({ name: name.trim(), allocation_ids: [...pick] }),
      }),
    onSuccess: (d) => {
      setCreateOpen(false);
      setFresh(d);
      qc.invalidateQueries({ queryKey: ["me", "credentials"] });
      toast({ title: "已建立 Codex 金鑰", description: "請立即複製 token，僅顯示一次" });
    },
    onError: (e) => toast({ title: "建立失敗", description: e.message, variant: "destructive" }),
  });

  return (
    <div className="container mx-auto py-8 space-y-6">
      <section>
        <h1 className="text-3xl font-bold tracking-tight">應用</h1>
        <p className="text-muted-foreground mt-2">
          把分配到的金鑰接上你慣用的工具。目前支援 Codex（更多應用陸續加入）。
        </p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Codex</CardTitle>
          <CardDescription>
            OpenAI 的 agent 工具——CLI、IDE 擴充、桌面 App 都能接上本平台（共用同一份設定）。
            Codex 需要「Agent 相容（Responses）」的模型。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 狀態 + 建金鑰捷徑 */}
          {allocsQuery.isSuccess && agentAllocs.length === 0 ? (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm">
              你目前沒有可用於 Codex 的模型（需要 Agent 相容的分配）。
              先到 <Link to="/catalog" className="underline">模型目錄</Link> 領取，或請管理員授權一個 Agent 相容的模型。
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="default">可用</Badge>
              <span className="text-sm text-muted-foreground">
                你有 {agentAllocs.length} 個 Agent 相容的模型可用於 Codex。
              </span>
              <Button size="sm" className="ml-auto" onClick={openCreate}>
                為 Codex 建金鑰
              </Button>
            </div>
          )}

          {/* 一鍵設定 */}
          <CodexInstallCard baseUrl={baseUrl} />
        </CardContent>
      </Card>

      {/* 建金鑰捷徑對話框：picker 只列 Agent 相容分配、預選 */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>為 Codex 建金鑰</DialogTitle>
            <DialogDescription>
              只列出 Agent 相容（Responses）的模型，避免挑到 Codex 接不上的。token 僅顯示一次。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label htmlFor="codex-key-name">名稱</Label>
              <Input id="codex-key-name" value={name} maxLength={64} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>可用模型（分配）</Label>
              {agentAllocs.map((a) => (
                <label key={a.id} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={pick.has(a.id)}
                    onCheckedChange={(c) =>
                      setPick((prev) => {
                        const next = new Set(prev);
                        if (c) next.add(a.id);
                        else next.delete(a.id);
                        return next;
                      })
                    }
                  />
                  <span>{a.display_name ?? a.resource_model}</span>
                  <code className="font-mono text-xs text-muted-foreground">{a.resource_model}</code>
                </label>
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>取消</Button>
            <Button
              disabled={!name.trim() || pick.size === 0 || createMut.isPending}
              onClick={() => createMut.mutate()}
            >
              {createMut.isPending ? "建立中…" : "建立"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 一次性 token 揭示 */}
      <AlertDialog open={!!fresh} onOpenChange={(o) => !o && setFresh(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>金鑰已建立——請立即複製</AlertDialogTitle>
            <AlertDialogDescription>
              這個 token 僅顯示一次。複製後貼進 Codex 設定，或用上面的一鍵安裝自動完成。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <code className="block break-all rounded bg-muted p-2 font-mono text-sm">{fresh?.token}</code>
          <AlertDialogFooter>
            <Button
              variant="outline"
              onClick={() => fresh && copyToClipboard(fresh.token).then(() => toast({ title: "已複製" }))}
            >
              複製 token
            </Button>
            <AlertDialogAction onClick={() => setFresh(null)}>完成</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
