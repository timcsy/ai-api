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
  kind,
}: {
  model: string;
  supportsResponses?: boolean;
  isEmbedding?: boolean;
  isOcr?: boolean;
  kind?: string;
}) {
  const { toast } = useToast();
  const [tab, setTab] = React.useState("curl");
  const base = apiBaseUrl();
  const m = model || "<model-slug>";

  // Phase 29 ③: image / rerank / TTS / STT — one compact "how to call" card each.
  const endpointInfo: Record<string, { path: string; desc: string; curl: string }> = {
    image: {
      path: "/images/generations", desc: "圖片生成模型",
      curl: `curl -X POST ${base}/images/generations \\
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\
  -d '{ "model": "${m}", "prompt": "a red dot" }'`,
    },
    rerank: {
      path: "/rerank", desc: "重排序（rerank）模型，依相關度排序候選文件",
      curl: `curl -X POST ${base}/rerank \\
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\
  -d '{ "model": "${m}", "query": "你的問題", "documents": ["文件A", "文件B"] }'`,
    },
    tts: {
      path: "/audio/speech", desc: "語音合成（TTS）模型，回傳音檔（audio/mpeg）",
      curl: `curl -X POST ${base}/audio/speech \\
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\
  -d '{ "model": "${m}", "input": "你好", "voice": "alloy" }' --output speech.mp3`,
    },
    stt: {
      path: "/audio/transcriptions", desc: "語音轉文字（STT）模型，上傳音檔取回文字",
      curl: `curl -X POST ${base}/audio/transcriptions \\
  -H "Authorization: Bearer $TOKEN" \\
  -F "model=${m}" -F "file=@audio.mp3"`,
    },
    moderation: {
      path: "/moderations", desc: "內容審核（moderation）模型，回傳安全分類",
      curl: `curl -X POST ${base}/moderations \\
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\
  -d '{ "model": "${m}", "input": "要審核的文字" }'`,
    },
    search: {
      path: "/search", desc: "網路搜尋（search）模型，依相關度回傳搜尋結果",
      curl: `curl -X POST ${base}/search \\
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\
  -d '{ "model": "${m}", "query": "你要搜尋的問題" }'`,
    },
    image_edit: {
      path: "/images/edits", desc: "圖片編輯（image edit）模型，上傳圖片 + 提示取回編輯後圖片",
      curl: `curl -X POST ${base}/images/edits \\
  -H "Authorization: Bearer $TOKEN" \\
  -F "model=${m}" -F "image=@input.png" -F "prompt=make it red"`,
    },
    realtime: {
      path: "/realtime",
      desc: "即時字幕（realtime）模型，用 WebSocket 串流音訊、即時收文字（OpenAI realtime transcription 相容）。用量按分鐘計",
      // WebSocket — not curl. Replace https:// with wss:// in the endpoint URL.
      curl: `# pip install websockets — 串麥克風 PCM、即時收字幕（把 https 換成 wss）
import asyncio, base64, json, websockets

async def main():
    url = "${base}/realtime".replace("https://", "wss://").replace("http://", "ws://")
    async with websockets.connect(url, additional_headers={"Authorization": "Bearer $TOKEN"}) as ws:
        await ws.send(json.dumps({"type": "session.update", "session": {
            "type": "transcription", "model": "${m}",
            "audio": {"input": {"format": {"type": "audio/pcm", "rate": 24000}}}}}))
        await ws.send(json.dumps({"type": "input_audio_buffer.append",
                                  "audio": base64.b64encode(pcm_chunk).decode()}))
        async for msg in ws:
            ev = json.loads(msg)
            if ev.get("type") == "conversation.item.input_audio_transcription.delta":
                print(ev["delta"], end="", flush=True)

asyncio.run(main())`,
    },
  };
  if (kind && endpointInfo[kind]) {
    const info = endpointInfo[kind]!;
    return (
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <div>
              <CardTitle className="text-lg">如何呼叫</CardTitle>
              <CardDescription>
                這是{info.desc}，端點 <code className="text-xs break-all">{base}{info.path}</code>；
                把 <code className="text-xs">$TOKEN</code> 換成你的金鑰 token。
              </CardDescription>
            </div>
            <Button
              variant="outline" size="sm" className="shrink-0"
              onClick={async () => {
                const ok = await copyToClipboard(info.curl);
                toast({ title: ok ? "已複製" : "複製失敗", variant: ok ? "default" : "destructive" });
              }}
            >
              複製
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">{info.curl}</pre>
        </CardContent>
      </Card>
    );
  }

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
