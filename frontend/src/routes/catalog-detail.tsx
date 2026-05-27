import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiUsageExample } from "@/components/api-usage-example";
import { ApiError, api } from "@/lib/api-client";
import { facetLabel } from "@/lib/catalog-labels";
import { per1kToPer1m } from "@/lib/price-format";

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
  price: { input_per_1k: string; output_per_1k: string } | null;
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
          <CardTitle className="text-lg">價格</CardTitle>
          <CardDescription>USD / 1M tokens（計費以呼叫當時的價目計算）</CardDescription>
        </CardHeader>
        <CardContent>
          {m.price ? (
            <div className="flex gap-8 text-sm">
              <div>
                <div className="text-xs text-muted-foreground">輸入</div>
                <div className="font-mono text-lg tabular-nums">${per1kToPer1m(m.price.input_per_1k)}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">輸出</div>
                <div className="font-mono text-lg tabular-nums">${per1kToPer1m(m.price.output_per_1k)}</div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">未定價（此模型的用量成本目前會算成 0）</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">說明</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="whitespace-pre-line text-sm">{m.description}</p>
        </CardContent>
      </Card>

      <ApiUsageExample model={m.slug} />

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
