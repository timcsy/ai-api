import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

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

/** Phase 36 (spec 050): the GitHub Copilot application detail — point VS Code
 * Copilot at the platform's OpenAI-compatible endpoint, create a scoped key.
 * Copilot lists models (GET /v1/models) and needs Responses-capable models, so
 * the create-key shortcut is scoped to Agent-compatible allocations. */
export function CopilotAppDetail() {
  const { member } = useAuth();
  const { toast } = useToast();
  const qc = useQueryClient();
  const baseUrl = member?.gateway_base_url ?? window.location.origin;
  const apiBase = `${baseUrl}/v1`;

  const allocsQuery = useQuery<Allocation[], ApiError>({
    queryKey: ["me", "allocations"],
    queryFn: () => api<Allocation[]>("/me/allocations"),
  });
  const agentAllocs = (allocsQuery.data ?? []).filter(
    (a) => a.status === "active" && a.agent_compatible,
  );

  const [createOpen, setCreateOpen] = React.useState(false);
  const [name, setName] = React.useState("Copilot");
  const [pick, setPick] = React.useState<Set<string>>(new Set());
  const [fresh, setFresh] = React.useState<Created | null>(null);

  const openCreate = () => {
    setName("Copilot");
    setPick(new Set(agentAllocs.map((a) => a.id)));
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
      toast({ title: "已建立 Copilot 金鑰", description: "請立即複製 token，僅顯示一次" });
    },
    onError: (e) => toast({ title: "建立失敗", description: e.message, variant: "destructive" }),
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">接上你的金鑰</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {allocsQuery.isSuccess && agentAllocs.length === 0 ? (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm">
              你目前沒有可用於 Copilot 的模型（需要 Agent 相容／Responses 的分配）。
              先到 <Link to="/catalog" className="underline">模型目錄</Link> 領取，或請管理員授權一個 Agent 相容的模型。
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="default">可用</Badge>
              <span className="text-sm text-muted-foreground">
                你有 {agentAllocs.length} 個 Agent 相容的模型可用於 Copilot。
              </span>
              <Button size="sm" className="ml-auto" onClick={openCreate}>
                為 Copilot 建金鑰
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">在 VS Code 設定 GitHub Copilot</CardTitle>
          <CardDescription>
            Copilot 支援自訂 OpenAI 相容模型；把端點指向本平台、填入金鑰即可。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <ol className="list-decimal space-y-2 pl-5">
            <li>
              在 Copilot 的「自訂模型 / OpenAI 相容」設定，API base URL 填{" "}
              <code className="break-all rounded bg-muted px-1 text-xs">{apiBase}</code>
            </li>
            <li>
              API key 填你上面建立的金鑰 token（<code className="text-xs">$TOKEN</code>）
            </li>
            <li>
              model 填模型 id——就是 <code className="break-all rounded bg-muted px-1 text-xs">{apiBase}/models</code>{" "}
              列出的某個 id（例如 <code className="text-xs">azure/gpt-5.4</code>）；別留空，否則會被擋下「模型不在範圍」
            </li>
          </ol>
          <div className="rounded-md border border-muted bg-muted/40 p-3 text-xs text-muted-foreground">
            <strong className="font-medium text-foreground">小提醒：</strong>
            伺服器端的對話記憶是「每個分配各自獨立」的。若你在同一把金鑰下
            <strong>跨 model 切換</strong>（＝切換分配）或對話過期，舊對話會接不上、平台會明確請你
            <strong>開新對話</strong>（而不是無聲地丟掉脈絡）——這是刻意的，避免「以為續接、其實失憶」。
          </div>
        </CardContent>
      </Card>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>為 Copilot 建金鑰</DialogTitle>
            <DialogDescription>
              只列出 Agent 相容（Responses）的模型，避免挑到 Copilot 接不上的。token 僅顯示一次。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label htmlFor="copilot-key-name">名稱</Label>
              <Input id="copilot-key-name" value={name} maxLength={64} onChange={(e) => setName(e.target.value)} />
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

      <AlertDialog open={!!fresh} onOpenChange={(o) => !o && setFresh(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>金鑰已建立——請立即複製</AlertDialogTitle>
            <AlertDialogDescription>
              這個 token 僅顯示一次。複製後貼進 Copilot 的 API key 設定。
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
