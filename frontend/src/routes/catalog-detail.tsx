import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { ApiError, api } from "@/lib/api-client";
import { facetLabel } from "@/lib/catalog-labels";
import { copyToClipboard } from "@/lib/clipboard";

interface ModelDetail {
  slug: string;
  display_name: string;
  family: string;
  description: string;
  modality_input: string[];
  modality_output: string[];
  capabilities: string[];
  context_window: number;
  cost_tier: string;
  recommended_for: string[];
  tags: string[];
  official_doc_url: string | null;
  status: string;
  deprecation_note: string | null;
  example_request: { curl?: string; body?: unknown; [k: string]: unknown };
}

export function CatalogDetailPage() {
  // /catalog/* — splat captures everything after /catalog/
  const location = useLocation();
  const slug = location.pathname.replace(/^\/catalog\//, "");

  const query = useQuery<ModelDetail, ApiError>({
    queryKey: ["catalog", "model", slug],
    queryFn: () => api<ModelDetail>(`/catalog/models/${slug}`),
    enabled: !!slug,
  });

  const { toast } = useToast();
  const handleCopy = async () => {
    const curl = query.data?.example_request.curl;
    if (!curl) {
      toast({ title: "無 curl 範例", description: "此模型未提供 curl 範例" });
      return;
    }
    const ok = await copyToClipboard(curl);
    toast({
      title: ok ? "已複製到剪貼簿" : "複製失敗",
      description: ok ? undefined : "請使用下方文字手動複製",
      variant: ok ? "default" : "destructive",
    });
  };

  if (query.error?.status === 404) {
    return (
      <div className="container mx-auto py-10 max-w-md text-center space-y-4">
        <h1 className="text-xl font-semibold">找不到模型「{slug}」</h1>
        <Button asChild variant="outline">
          <Link to="/catalog">回目錄</Link>
        </Button>
      </div>
    );
  }

  if (query.isLoading) {
    return <div className="container mx-auto py-10 text-muted-foreground">載入中…</div>;
  }

  if (!query.data) {
    return null;
  }

  const m = query.data;
  const curl = m.example_request.curl ?? "";
  const body = m.example_request.body ? JSON.stringify(m.example_request.body, null, 2) : "";

  return (
    <div className="container mx-auto py-8 max-w-4xl space-y-6">
      <Link to="/catalog" className="text-sm text-muted-foreground hover:underline">
        ← 回目錄
      </Link>

      {m.status === "deprecated" && (
        <Alert variant="destructive">
          <AlertTitle>此模型已停用</AlertTitle>
          <AlertDescription>{m.deprecation_note}</AlertDescription>
        </Alert>
      )}

      <section className="space-y-2">
        <h1 className="text-3xl font-bold">{m.display_name}</h1>
        <p className="text-muted-foreground font-mono text-sm">{m.slug}</p>
        <div className="flex flex-wrap gap-2 mt-2">
          <Badge>成本：{facetLabel(m.cost_tier)}</Badge>
          <Badge variant="secondary">{m.family}</Badge>
          <Badge variant="outline">{m.context_window.toLocaleString()} tokens</Badge>
          {m.capabilities.map((c) => (
            <Badge key={c} variant="outline">{facetLabel(c)}</Badge>
          ))}
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">說明</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="whitespace-pre-line text-sm">{m.description}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">使用範例</CardTitle>
            <Button size="sm" onClick={() => void handleCopy()}>
              複製 curl
            </Button>
          </div>
          <CardDescription>把 $TOKEN 換成你的分配 token 即可執行</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="curl">
            <TabsList>
              <TabsTrigger value="curl">curl</TabsTrigger>
              <TabsTrigger value="python">Python</TabsTrigger>
              <TabsTrigger value="javascript">JavaScript</TabsTrigger>
              <TabsTrigger value="json">JSON body</TabsTrigger>
            </TabsList>
            <TabsContent value="curl">
              <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">{curl}</pre>
            </TabsContent>
            <TabsContent value="python">
              <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">
{`from openai import OpenAI

client = OpenAI(
    base_url="${window.location.origin}/v1",
    api_key="$YOUR_TOKEN",
)
resp = client.chat.completions.create(
    model="${m.slug.split("/").pop() ?? m.slug}",
    messages=[{"role": "user", "content": "你好"}],
)
print(resp.choices[0].message.content)`}
              </pre>
            </TabsContent>
            <TabsContent value="javascript">
              <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">
{`const res = await fetch("${window.location.origin}/v1/chat/completions", {
  method: "POST",
  headers: {
    "Authorization": "Bearer " + process.env.YOUR_TOKEN,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model: "${m.slug.split("/").pop() ?? m.slug}",
    messages: [{ role: "user", content: "你好" }],
  }),
});
const data = await res.json();
console.log(data.choices[0].message.content);`}
              </pre>
            </TabsContent>
            <TabsContent value="json">
              <pre className="bg-muted rounded-md p-3 text-xs overflow-x-auto">{body}</pre>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {m.official_doc_url && (
        <p className="text-sm">
          <a
            href={m.official_doc_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary underline"
          >
            官方文件 →
          </a>
        </p>
      )}
    </div>
  );
}
