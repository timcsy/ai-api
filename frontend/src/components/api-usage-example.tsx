import * as React from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { apiBaseUrl } from "@/lib/api-base";
import { copyToClipboard } from "@/lib/clipboard";
import { triggerDownload } from "@/lib/download";

/**
 * One consistent "how to call the API" block shared by the allocation-detail
 * and catalog-detail pages, so the two never drift apart again.
 *
 * - `model`: the full catalog slug (what the API expects, e.g. "azure/gpt-5.4-mini").
 * - `supportsResponses`: when true, also show /v1/responses + Codex examples.
 * - The token is always shown as the `$TOKEN` placeholder — the real token is
 *   only revealed once at allocation creation, never re-fetchable.
 */
export function ApiUsageExample({
  model,
  supportsResponses = false,
}: {
  model: string;
  supportsResponses?: boolean;
}) {
  const { toast } = useToast();
  const [tab, setTab] = React.useState("curl");
  const base = apiBaseUrl();
  const m = model || "<model-slug>";

  const snippets: Record<string, string> = {
    curl: `curl -X POST ${base}/chat/completions \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${m}",
    "messages": [{"role": "user", "content": "你好"}]
  }'`,
    python: `from openai import OpenAI

client = OpenAI(
    base_url="${base}",
    api_key="$TOKEN",
)
resp = client.chat.completions.create(
    model="${m}",
    messages=[{"role": "user", "content": "你好"}],
)
print(resp.choices[0].message.content)`,
    javascript: `const res = await fetch("${base}/chat/completions", {
  method: "POST",
  headers: {
    "Authorization": "Bearer $TOKEN",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model: "${m}",
    messages: [{ role: "user", content: "你好" }],
  }),
});
const data = await res.json();
console.log(data.choices[0].message.content);`,
    json: `{
  "model": "${m}",
  "messages": [{"role": "user", "content": "你好"}]
}`,
  };

  if (supportsResponses) {
    snippets.responses = `curl -N -X POST ${base}/responses \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${m}",
    "input": "你好",
    "stream": true
  }'`;
    snippets["responses-py"] = `from openai import OpenAI

client = OpenAI(
    base_url="${base}",
    api_key="$TOKEN",
)
resp = client.responses.create(
    model="${m}",
    input="你好",
)
print(resp.output_text)`;
    snippets.codex = `model = "${m}"
model_provider = "ccsh"

[model_providers.ccsh]
name = "CCSH AI Gateway"
base_url = "${base}"
wire_api = "responses"
env_key = "CCSH_AI_TOKEN"
`;
  }

  const downloadCodexConfig = () => {
    triggerDownload("config.toml", new Blob([snippets.codex ?? ""], { type: "text/plain" }));
    toast({ title: "已下載 config.toml", description: "依下方步驟放到 Codex 設定資料夾" });
  };

  const tabKeys = supportsResponses
    ? (["curl", "python", "javascript", "json", "responses", "responses-py", "codex"] as const)
    : (["curl", "python", "javascript", "json"] as const);

  const TAB_LABEL: Record<string, string> = {
    curl: "curl",
    python: "Python",
    javascript: "JavaScript",
    json: "JSON body",
    responses: "Responses (curl)",
    "responses-py": "Responses (Py)",
    codex: "Codex",
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-lg">如何呼叫</CardTitle>
            <CardDescription>
              端點 <code className="text-xs">{base}</code>；把 <code className="text-xs">$TOKEN</code> 換成你的分配 token（放 Authorization: Bearer）。
              {supportsResponses && (
                <>
                  {" "}此模型支援 <code className="text-xs">/responses</code>，可給 OpenAI Codex 等 agent 工具使用（見 Codex 分頁）。
                </>
              )}
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="shrink-0"
            onClick={async () => {
              const ok = await copyToClipboard(snippets[tab] ?? snippets.curl!);
              toast({
                title: ok ? "已複製" : "複製失敗",
                description: ok ? undefined : "請手動選取下方文字複製",
                variant: ok ? "default" : "destructive",
              });
            }}
          >
            複製
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="flex-wrap h-auto">
            {tabKeys.map((k) => (
              <TabsTrigger key={k} value={k}>{TAB_LABEL[k]}</TabsTrigger>
            ))}
          </TabsList>
          {tabKeys.map((k) => (
            <TabsContent key={k} value={k}>
              {k === "codex" ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-muted-foreground">下方是 Codex 設定檔內容（<code>config.toml</code>）。</span>
                    <Button size="sm" variant="outline" className="shrink-0" onClick={downloadCodexConfig}>
                      下載 config.toml
                    </Button>
                  </div>
                  <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">{snippets.codex}</pre>
                  <CodexSetupSteps token="$TOKEN" />
                </div>
              ) : (
                <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">{snippets[k]}</pre>
              )}
            </TabsContent>
          ))}
        </Tabs>
      </CardContent>
    </Card>
  );
}

/** Per-OS install + setup steps after downloading config.toml. */
function CodexSetupSteps({ token }: { token: string }) {
  const [os, setOs] = React.useState<"mac" | "linux" | "windows">("mac");
  const homePath =
    os === "windows" ? "%USERPROFILE%\\.codex\\config.toml" : "~/.codex/config.toml";
  const mkdir =
    os === "windows"
      ? `mkdir %USERPROFILE%\\.codex`
      : `mkdir -p ~/.codex`;
  const move =
    os === "windows"
      ? `move %USERPROFILE%\\Downloads\\config.toml %USERPROFILE%\\.codex\\config.toml`
      : `mv ~/Downloads/config.toml ~/.codex/config.toml`;
  const setToken =
    os === "windows"
      ? `setx CCSH_AI_TOKEN "${token}"   # 重開終端機後生效`
      : `export CCSH_AI_TOKEN="${token}"   # 可寫進 ~/.zshrc 或 ~/.bashrc`;

  return (
    <div className="rounded-md border p-3 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium">安裝與使用步驟</span>
        <div className="flex gap-1">
          {(["mac", "linux", "windows"] as const).map((o) => (
            <Button key={o} size="sm" variant={o === os ? "default" : "outline"}
              className="h-6 px-2 text-xs" onClick={() => setOs(o)}>
              {o === "mac" ? "macOS" : o === "linux" ? "Linux" : "Windows"}
            </Button>
          ))}
        </div>
      </div>
      <ol className="list-decimal pl-5 text-xs space-y-1.5 text-muted-foreground">
        <li>
          安裝 Codex CLI（需先有 Node.js）：
          <pre className="mt-1 bg-muted rounded p-2 overflow-x-auto">npm install -g @openai/codex</pre>
          {os === "mac" && <span>（或 <code>brew install codex</code>）</span>}
        </li>
        <li>
          建立設定資料夾並把剛下載的 <code>config.toml</code> 放進去（路徑：<code>{homePath}</code>）：
          <pre className="mt-1 bg-muted rounded p-2 overflow-x-auto">{`${mkdir}\n${move}`}</pre>
        </li>
        <li>
          設定你的憑證 token（把 <code>{token}</code> 換成你的分配 token）：
          <pre className="mt-1 bg-muted rounded p-2 overflow-x-auto">{setToken}</pre>
        </li>
        <li>
          開始使用：
          <pre className="mt-1 bg-muted rounded p-2 overflow-x-auto">codex "在這個資料夾建一個 hello.py 並執行"</pre>
        </li>
      </ol>
    </div>
  );
}
