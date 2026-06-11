import * as React from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { apiBaseUrl } from "@/lib/api-base";
import { copyToClipboard } from "@/lib/clipboard";

/**
 * One consistent "how to call the API" block shared by the allocation-detail
 * and catalog-detail pages, so the two never drift apart again.
 *
 * - `model`: the full catalog slug (what the API expects, e.g. "azure/gpt-5.4-mini").
 * - `supportsResponses`: when true, also show /v1/responses examples.
 * - The token is always shown as the `$TOKEN` placeholder — the real token is
 *   only revealed once at creation, never re-fetchable.
 *
 * Phase 20: Codex setup lives in one place (the dashboard "安裝 Codex" one-liner
 * + device-flow), so the old per-model Codex config tab was removed here.
 */
export function ApiUsageExample({
  model,
  supportsResponses = false,
  isEmbedding = false,
  isOcr = false,
}: {
  model: string;
  supportsResponses?: boolean;
  isEmbedding?: boolean;
  isOcr?: boolean;
}) {
  const { toast } = useToast();
  const [tab, setTab] = React.useState("curl");
  const base = apiBaseUrl();
  const m = model || "<model-slug>";

  // Phase 29 ②: OCR models call /v1/ocr with {model, document}.
  if (isOcr) {
    const ocrSnippets: Record<string, string> = {
      curl: `curl -X POST ${base}/ocr \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${m}",
    "document": { "type": "document_url", "document_url": "https://…/file.pdf" }
  }'`,
      python: `from openai import OpenAI

client = OpenAI(base_url="${base}", api_key="$TOKEN")
resp = client.post(
    "/ocr",
    body={
        "model": "${m}",
        "document": {"type": "document_url", "document_url": "https://…/file.pdf"},
    },
    cast_to=dict,
)
print(resp["pages"])`,
      json: `{
  "model": "${m}",
  "document": { "type": "document_url", "document_url": "https://…/file.pdf" }
}`,
    };
    const ocrKeys = ["curl", "python", "json"] as const;
    const ocrLabel: Record<string, string> = { curl: "curl", python: "Python", json: "JSON body" };
    return (
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <div>
              <CardTitle className="text-lg">如何呼叫</CardTitle>
              <CardDescription>
                這是文件辨識（OCR）模型，端點 <code className="text-xs break-all">{base}/ocr</code>；
                送一份文件（URL 或 base64）取回辨識文字，計費以「頁」計。把 <code className="text-xs">$TOKEN</code> 換成你的金鑰 token。
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="shrink-0"
              onClick={async () => {
                const ok = await copyToClipboard(ocrSnippets[tab] ?? ocrSnippets.curl!);
                toast({ title: ok ? "已複製" : "複製失敗", variant: ok ? "default" : "destructive" });
              }}
            >
              複製
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={ocrKeys.includes(tab as (typeof ocrKeys)[number]) ? tab : "curl"} onValueChange={setTab}>
            <TabsList className="flex-wrap h-auto">
              {ocrKeys.map((k) => (
                <TabsTrigger key={k} value={k}>{ocrLabel[k]}</TabsTrigger>
              ))}
            </TabsList>
            {ocrKeys.map((k) => (
              <TabsContent key={k} value={k}>
                <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">{ocrSnippets[k]}</pre>
              </TabsContent>
            ))}
          </Tabs>
        </CardContent>
      </Card>
    );
  }

  // Phase 29: embedding models call /v1/embeddings with {model, input}.
  if (isEmbedding) {
    const embSnippets: Record<string, string> = {
      curl: `curl -X POST ${base}/embeddings \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${m}",
    "input": "你好"
  }'`,
      python: `from openai import OpenAI

client = OpenAI(
    base_url="${base}",
    api_key="$TOKEN",
)
resp = client.embeddings.create(
    model="${m}",
    input="你好",
)
print(resp.data[0].embedding)`,
      javascript: `const res = await fetch("${base}/embeddings", {
  method: "POST",
  headers: {
    "Authorization": "Bearer $TOKEN",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model: "${m}",
    input: "你好",
  }),
});
const data = await res.json();
console.log(data.data[0].embedding);`,
      json: `{
  "model": "${m}",
  "input": "你好"
}`,
    };
    const embKeys = ["curl", "python", "javascript", "json"] as const;
    const embLabel: Record<string, string> = {
      curl: "curl", python: "Python", javascript: "JavaScript", json: "JSON body",
    };
    return (
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <div>
              <CardTitle className="text-lg">如何呼叫</CardTitle>
              <CardDescription>
                這是向量（embedding）模型，端點 <code className="text-xs break-all">{base}/embeddings</code>；
                把 <code className="text-xs">$TOKEN</code> 換成你的金鑰 token。
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="shrink-0"
              onClick={async () => {
                const ok = await copyToClipboard(embSnippets[tab] ?? embSnippets.curl!);
                toast({ title: ok ? "已複製" : "複製失敗", variant: ok ? "default" : "destructive" });
              }}
            >
              複製
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={embKeys.includes(tab as (typeof embKeys)[number]) ? tab : "curl"} onValueChange={setTab}>
            <TabsList className="flex-wrap h-auto">
              {embKeys.map((k) => (
                <TabsTrigger key={k} value={k}>{embLabel[k]}</TabsTrigger>
              ))}
            </TabsList>
            {embKeys.map((k) => (
              <TabsContent key={k} value={k}>
                <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">{embSnippets[k]}</pre>
              </TabsContent>
            ))}
          </Tabs>
        </CardContent>
      </Card>
    );
  }

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
  }

  const tabKeys = supportsResponses
    ? (["curl", "python", "javascript", "json", "responses", "responses-py"] as const)
    : (["curl", "python", "javascript", "json"] as const);

  const TAB_LABEL: Record<string, string> = {
    curl: "curl",
    python: "Python",
    javascript: "JavaScript",
    json: "JSON body",
    responses: "Responses (curl)",
    "responses-py": "Responses (Py)",
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-lg">如何呼叫</CardTitle>
            <CardDescription>
              端點 <code className="text-xs break-all">{base}</code>；把 <code className="text-xs">$TOKEN</code> 換成你的金鑰 token（放 Authorization: Bearer）。
              {supportsResponses && (
                <>
                  {" "}此模型支援 <code className="text-xs">/responses</code>；要用 OpenAI Codex 請到儀表板的「安裝 Codex（一行指令）」。
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
              <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">{snippets[k]}</pre>
            </TabsContent>
          ))}
        </Tabs>
      </CardContent>
    </Card>
  );
}
