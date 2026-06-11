import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { ApiUsageExample } from "@/components/api-usage-example";
import { ApiError, api } from "@/lib/api-client";
import { facetHint, facetLabel } from "@/lib/catalog-labels";
import { per1kToPer1m } from "@/lib/price-format";
import { copyToClipboard } from "@/lib/clipboard";
import { familyLabel, statusLabel } from "@/lib/status-label";

interface MyAllocation {
  id: string;
  resource_model: string;
  status: string;
}
interface ClaimableModel {
  slug: string;
  state: "claimable" | "already_claimed" | "reclaim_locked";
}

interface ModelDetail {
  slug: string;
  display_name: string;
  family: string;
  description: string;
  modality_input: string[];
  modality_output: string[];
  capabilities: string[];
  responses_support?: {
    state: "available" | "unavailable" | "unknown";
    source: "tested" | "manual" | null;
  };
  kind?: "chat" | "embedding" | "tts" | "image" | "stt" | "ocr" | "unknown";
  context_window: number;
  cost_tier: string;
  recommended_for: string[];
  tags: string[];
  official_doc_url: string | null;
  status: string;
  deprecation_note: string | null;
  example_request: { curl?: string; body?: unknown; [k: string]: unknown };
  price: { input_per_1k: string; output_per_1k: string; cached_input_per_1k?: string } | null;
}

export function CatalogDetailPage() {
  // /catalog/* — splat captures everything after /catalog/
  const location = useLocation();
  const slug = location.pathname.replace(/^\/catalog\//, "");

  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [tokenDialog, setTokenDialog] = React.useState<string | null>(null);

  const query = useQuery<ModelDetail, ApiError>({
    queryKey: ["catalog", "model", slug],
    queryFn: () => api<ModelDetail>(`/catalog/models/${slug}`),
    enabled: !!slug,
  });

  // A+C: surface the member's relationship to this model (held → link to the
  // allocation; claimable → claim here; otherwise just catalog info).
  const myAllocsQuery = useQuery<MyAllocation[], ApiError>({
    queryKey: ["me", "allocations"],
    queryFn: () => api<MyAllocation[]>("/me/allocations"),
    enabled: !!slug,
  });
  const claimableQuery = useQuery<ClaimableModel[], ApiError>({
    queryKey: ["me", "claimable-models"],
    queryFn: () => api<ClaimableModel[]>("/me/claimable-models"),
    enabled: !!slug,
  });
  const heldAlloc = (myAllocsQuery.data ?? []).find(
    (a) => a.resource_model === slug && a.status === "active",
  );
  const claimable = (claimableQuery.data ?? []).find((c) => c.slug === slug);

  const claimMut = useMutation<{ token: string }, ApiError, void>({
    mutationFn: () =>
      api<{ token: string }>("/me/allocations", {
        method: "POST",
        body: JSON.stringify({ model: slug }),
      }),
    onSuccess: (r) => {
      setTokenDialog(r.token);
      queryClient.invalidateQueries({ queryKey: ["me", "allocations"] });
      queryClient.invalidateQueries({ queryKey: ["me", "claimable-models"] });
    },
    onError: (e) => toast({ title: "領取失敗", description: e.message, variant: "destructive" }),
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
        <p className="text-muted-foreground font-mono text-sm break-all">{m.slug}</p>
        <div className="flex flex-wrap gap-2 mt-2">
          <Badge>成本：{facetLabel(m.cost_tier)}</Badge>
          <Badge variant="secondary">{familyLabel(m.family)}</Badge>
          <Badge variant="outline">上下文 {m.context_window.toLocaleString()} tokens</Badge>
          {m.capabilities.map((c) => {
            if (c === "responses") {
              const src = m.responses_support?.source;
              const srcLabel = src === "tested" ? "實測" : src === "manual" ? "手動" : null;
              return (
                <Badge key={c} variant="outline" title={facetHint(c)} className="cursor-help">
                  {facetLabel(c)}
                  {srcLabel ? `・${srcLabel}` : ""}
                </Badge>
              );
            }
            return (
              <Badge key={c} variant="outline" title={facetHint(c)} className="cursor-help">
                {facetLabel(c)}
              </Badge>
            );
          })}
        </div>
      </section>

      {/* A+C: your relationship to this model */}
      {heldAlloc ? (
        <Card className="border-primary/40">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
            <div className="text-sm min-w-0">
              <span className="font-medium">你已領取此模型</span>
              <Badge variant="default" className="ml-2">{statusLabel(heldAlloc.status)}</Badge>
              <p className="text-xs text-muted-foreground mt-1">用 token 呼叫即可；憑證與用量在儀表板管理。</p>
            </div>
            <Button asChild variant="outline" size="sm" className="shrink-0">
              <Link to={`/dashboard/allocations/${heldAlloc.id}`}>查看憑證與用量 →</Link>
            </Button>
          </CardContent>
        </Card>
      ) : claimable?.state === "claimable" ? (
        <Card className="border-primary/40">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
            <div className="text-sm min-w-0">
              <span className="font-medium">此模型開放自助領取</span>
              <p className="text-xs text-muted-foreground mt-1">一鍵領取一張可呼叫的憑證（token 只顯示一次）。</p>
            </div>
            <Button size="sm" className="shrink-0" disabled={claimMut.isPending} onClick={() => claimMut.mutate()}>
              領取憑證
            </Button>
          </CardContent>
        </Card>
      ) : claimable?.state === "reclaim_locked" ? (
        <Card>
          <CardContent className="py-4 text-sm">
            <span className="font-medium">自助領取已鎖定</span>
            <p className="text-xs text-muted-foreground mt-1">先前的憑證被撤回，需管理員解鎖後才能再次領取。</p>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">價格</CardTitle>
          <CardDescription>USD / 1M tokens（計費以呼叫當時的價目計算）</CardDescription>
        </CardHeader>
        <CardContent>
          {m.price ? (
            <div className="flex flex-wrap gap-x-8 gap-y-3 text-sm">
              <div>
                <div className="text-xs text-muted-foreground">輸入</div>
                <div className="font-mono text-lg tabular-nums">${per1kToPer1m(m.price.input_per_1k)}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">輸出</div>
                <div className="font-mono text-lg tabular-nums">${per1kToPer1m(m.price.output_per_1k)}</div>
              </div>
              {m.price.cached_input_per_1k && (
                <div>
                  <div className="text-xs text-muted-foreground">快取輸入</div>
                  <div className="font-mono text-lg tabular-nums">${per1kToPer1m(m.price.cached_input_per_1k)}</div>
                </div>
              )}
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

      <ApiUsageExample
        model={m.slug}
        supportsResponses={m.capabilities.includes("responses")}
        isEmbedding={m.kind === "embedding"}
        isOcr={m.kind === "ocr"}
      />

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

      <Dialog open={!!tokenDialog} onOpenChange={(open) => !open && setTokenDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>憑證已領取 — 此 token 只顯示一次</DialogTitle>
            <DialogDescription>請立即複製並安全保存。關閉後無法再次取得。</DialogDescription>
          </DialogHeader>
          <pre className="bg-muted p-3 rounded text-xs overflow-x-auto break-all">{tokenDialog}</pre>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={async () => {
                if (tokenDialog) await copyToClipboard(tokenDialog);
                toast({ title: "已複製" });
              }}
            >
              複製
            </Button>
            <Button onClick={() => setTokenDialog(null)}>我已複製</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
