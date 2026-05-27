import * as React from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { copyToClipboard } from "@/lib/clipboard";

/**
 * One consistent "how to call the API" block shared by the allocation-detail
 * and catalog-detail pages, so the two never drift apart again.
 *
 * - `model`: the full catalog slug (what the API expects, e.g. "azure/gpt-5.4-mini").
 * - The token is always shown as the `$TOKEN` placeholder — the real token is
 *   only revealed once at allocation creation, never re-fetchable.
 */
export function ApiUsageExample({ model }: { model: string }) {
  const { toast } = useToast();
  const [tab, setTab] = React.useState("curl");
  const base = `${window.location.origin}/v1`;
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

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-lg">如何呼叫</CardTitle>
            <CardDescription>
              端點 <code className="text-xs">{base}</code>；把 <code className="text-xs">$TOKEN</code> 換成你的分配 token（放 Authorization: Bearer）。
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
          <TabsList>
            <TabsTrigger value="curl">curl</TabsTrigger>
            <TabsTrigger value="python">Python</TabsTrigger>
            <TabsTrigger value="javascript">JavaScript</TabsTrigger>
            <TabsTrigger value="json">JSON body</TabsTrigger>
          </TabsList>
          {(["curl", "python", "javascript", "json"] as const).map((k) => (
            <TabsContent key={k} value={k}>
              <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">{snippets[k]}</pre>
            </TabsContent>
          ))}
        </Tabs>
      </CardContent>
    </Card>
  );
}
