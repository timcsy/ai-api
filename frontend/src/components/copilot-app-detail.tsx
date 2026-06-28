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

/** Build the `models` array for VS Code's chatLanguageModels.json, pre-filled with
 * the key's scoped models. `url` is the BASE (…/v1) — Copilot appends the path per
 * apiType. id = canonical resource_model (always routable; matches /v1/models). */
function buildModelsJson(models: string[], apiBase: string): string {
  return JSON.stringify(
    models.map((id) => ({
      id,
      name: id,
      url: apiBase,
      toolCalling: true,
      maxInputTokens: 128000,
      maxOutputTokens: 16000,
    })),
    null,
    2,
  );
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
  const [freshModels, setFreshModels] = React.useState<string[]>([]);

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
      setFreshModels(agentAllocs.filter((a) => pick.has(a.id)).map((a) => a.resource_model));
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
          <CardTitle className="text-base">在 VS Code 設定 GitHub Copilot（自訂模型 / BYOK）</CardTitle>
          <CardDescription>
            VS Code 1.122+ 的 Copilot Chat 可加入「自訂 OpenAI 相容模型」；設定一次，模型就會出現在
            Chat 的模型選單。以下為**已在真機驗證**的設定（不同版本標籤可能略有差異）。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <ol className="list-decimal space-y-2 pl-5">
            <li>
              先在上方「接上你的金鑰」建立一把金鑰，拿到 token（<strong>只顯示一次</strong>，請先複製）。
            </li>
            <li>
              VS Code 開命令面板（<code className="text-xs">⌘/Ctrl + Shift + P</code>）→ 執行{" "}
              <strong>Chat: Manage Language Models</strong>（管理語言模型）。
            </li>
            <li>
              供應商選 <strong>Custom Endpoint</strong>（自訂端點）。
              <span className="text-muted-foreground">（較舊版 Copilot 可能顯示為「OpenAI Compatible」，欄位類似。）</span>
            </li>
            <li>
              依提示填 <strong>Name</strong>（隨意）、<strong>API Key</strong>（貼上步驟 1 的金鑰；VS Code 會存成 secret、不寫明文進檔）、
              <strong>API Type</strong> 選 <strong>Responses</strong>（實測可用）。
            </li>
            <li>
              VS Code 接著開 <code className="text-xs">chatLanguageModels.json</code>——外層 provider 它已建好，
              你在 <code className="text-xs">models</code> 陣列加入要用的模型。<strong>實測可用的範例</strong>：
            </li>
          </ol>
          <pre className="overflow-x-auto rounded bg-muted p-3 text-xs leading-relaxed">{`[
  {
    "name": "Custom Endpoint",
    "vendor": "customendpoint",
    "apiKey": "\${input:chat.lm.secret.xxxx}",
    "apiType": "responses",
    "models": [
      {
        "id": "gpt-5.4",
        "name": "gpt-5.4",
        "url": "${apiBase}",
        "toolCalling": true,
        "vision": true,
        "maxInputTokens": 128000,
        "maxOutputTokens": 16000
      }
    ]
  }
]`}</pre>
          <p className="rounded-md border border-amber-300 bg-amber-50 p-2 text-xs">
            <strong>最容易填錯的地方</strong>：<code className="text-xs">url</code> 只填到 base{" "}
            <code className="break-all text-xs">{apiBase}</code>（到 <code className="text-xs">/v1</code> 為止），
            <strong>不要</strong>自己接 <code className="text-xs">/chat/completions</code> 或 <code className="text-xs">/responses</code>——
            Copilot 會依 <code className="text-xs">apiType</code> 自動接（<code className="text-xs">responses</code> → <code className="text-xs">/v1/responses</code>）。
          </p>
          <ol className="list-decimal space-y-2 pl-5" start={6}>
            <li>存檔 → 回到 Chat，模型選單就會出現你的模型，選它即可開始對話。</li>
          </ol>

          <ul className="space-y-1 rounded-md border border-muted bg-muted/40 p-3 text-xs text-muted-foreground">
            <li>
              <strong className="text-foreground">模型 id</strong>：用你在「<strong>分配</strong>」頁看到的模型名稱
              （建金鑰時的清單也會列出）。前綴可省略——無歧義時直接寫 <code className="text-xs">gpt-5.4</code> 即可（如上例），
              寫完整 <code className="text-xs">azure/gpt-5.4</code> 也行；填錯或留空才會被擋「模型不在範圍」。
            </li>
            <li>
              <strong className="text-foreground">apiType</strong>：<code className="text-xs">responses</code> 實測可用（本平台高保真路徑）；
              也可在 wizard 改選 <strong>Chat Completions</strong>（無狀態、無下方限制）。url 一律填 base、端點由 apiType 決定。
            </li>
            <li>
              每個模型 <code className="text-xs">toolCalling: true</code> 才能在 agent 模式選；
              <code className="text-xs">vision</code> 依該模型是否支援圖片輸入。
            </li>
            <li>
              BYOK 只作用在 <strong className="text-foreground">Chat</strong>（不含行內補全 inline completions）；用量計入你在本平台的分配額度。
            </li>
          </ul>

          <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs">
            <strong className="font-medium">跨分配對話的限制（用 Responses 時）：</strong>
            伺服器端對話記憶（<code className="text-xs">store</code>）是「<strong>每個分配各自獨立</strong>」的。
            若你設了多個模型、在同一把金鑰下<strong>跨 model 切換</strong>（＝切換分配）或對話過期，舊對話會接不上，
            平台會明確請你 <strong>開新對話</strong>（而非無聲丟掉脈絡）——避免「以為續接、其實失憶」。
            把 API Type 設 <strong>Chat Completions</strong>（無狀態）則沒有這個問題。
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
              token 僅顯示一次。下面也幫你把 Copilot 的模型設定填好了。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-3">
            <div>
              <div className="mb-1 text-xs font-medium">① API Key（貼進 Custom Endpoint 的 API Key 欄）</div>
              <code className="block break-all rounded bg-muted p-2 font-mono text-sm">{fresh?.token}</code>
              <Button
                variant="outline"
                size="sm"
                className="mt-1"
                onClick={() => fresh && copyToClipboard(fresh.token).then(() => toast({ title: "已複製 token" }))}
              >
                複製 token
              </Button>
            </div>
            {freshModels.length > 0 && (
              <div>
                <div className="mb-1 text-xs font-medium">
                  ② <code className="text-xs">chatLanguageModels.json</code> 的 <code className="text-xs">models</code>
                  （已填好你的 {freshModels.length} 個模型）
                </div>
                <pre className="max-h-48 overflow-auto rounded bg-muted p-2 text-xs leading-relaxed">
                  {buildModelsJson(freshModels, apiBase)}
                </pre>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-1"
                  onClick={() =>
                    copyToClipboard(buildModelsJson(freshModels, apiBase)).then(() =>
                      toast({ title: "已複製 models 設定" }),
                    )
                  }
                >
                  複製 models 設定
                </Button>
                <p className="mt-1 text-xs text-muted-foreground">
                  在 wizard 建好 Custom Endpoint 後，把它的 <code className="text-xs">models</code> 換成這段——
                  你全部的模型就會出現在 Chat 的模型選單，用選的即可。
                </p>
              </div>
            )}
          </div>
          <AlertDialogFooter>
            <AlertDialogAction onClick={() => setFresh(null)}>完成</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
