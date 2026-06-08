import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  RadioGroup,
  RadioGroupItem,
} from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { VisibilityDiagnose } from "@/components/visibility-diagnose";
import { FieldSourceBadge, type FieldSource } from "@/components/field-source-badge";
import { LiteLLMRawPanel } from "@/components/litellm-raw-panel";
import { LiteLLMUpdateDiff } from "@/components/litellm-update-diff";
import { per1kToPer1m } from "@/lib/price-format";
import { ApiError, api } from "@/lib/api-client";

interface Visibility {
  provider_has_credential: boolean;
  visible_member_count: number;
  total_active_members: number;
  allocation_count: number;
}

interface CatalogModel {
  slug: string;
  provider: string;
  display_name: string;
  family: string;
  description: string;
  context_window: number;
  cost_tier: string;
  status: string;
  modality_input: string[];
  modality_output: string[];
  capabilities: string[];
  responses_support?: {
    state: "available" | "unavailable" | "unknown";
    source: "tested" | "manual" | null;
  };
  test_kind?: "chat" | "embedding" | "tts" | "image" | "stt" | "unknown";
  test_billable?: boolean;
  test_supported?: boolean;
  recommended_for: string[];
  tags: string[];
  default_access: "open" | "restricted";
  allowed_tags: string[];
  denied_tags: string[];
  self_service_enabled: boolean;
  self_service_default_quota: number | null;
  price: { input_per_1k: string; output_per_1k: string; cached_input_per_1k?: string } | null;
  visibility?: Visibility;
  litellm_sync?: {
    base_model_key: string;
    imported_version: string;
    field_sources: Record<string, FieldSource>;
    snapshot: Record<string, unknown>;
    raw: Record<string, unknown> | null;
  } | null;
}

export function AdminModelDetailPage() {
  const location = useLocation();
  const slug = location.pathname.replace(/^\/admin\/model\//, "");

  const queryClient = useQueryClient();
  const { toast } = useToast();

  const modelsQuery = useQuery<CatalogModel[], ApiError>({
    queryKey: ["admin", "catalog-models-admin"],
    queryFn: () => api<CatalogModel[]>("/admin/catalog/models"),
  });
  const model = modelsQuery.data?.find((m) => m.slug === slug);

  const [defaultAccess, setDefaultAccess] = React.useState<"open" | "restricted">("open");
  const [allowedTags, setAllowedTags] = React.useState<string[]>([]);
  const [deniedTags, setDeniedTags] = React.useState<string[]>([]);
  const [allowInput, setAllowInput] = React.useState("");
  const [denyInput, setDenyInput] = React.useState("");
  const [ssEnabled, setSsEnabled] = React.useState(false);
  const [ssQuota, setSsQuota] = React.useState("");
  const seededRef = React.useRef(false);
  React.useEffect(() => {
    if (model && !seededRef.current) {
      setDefaultAccess(model.default_access);
      setAllowedTags([...model.allowed_tags]);
      setDeniedTags([...model.denied_tags]);
      setSsEnabled(model.self_service_enabled);
      setSsQuota(model.self_service_default_quota?.toString() ?? "");
      seededRef.current = true;
    }
  }, [model]);

  const ssMut = useMutation<unknown, ApiError, void>({
    mutationFn: () =>
      api(`/admin/catalog/models/${slug}/self-service`, {
        method: "PATCH",
        body: JSON.stringify({
          enabled: ssEnabled,
          default_quota: ssEnabled && ssQuota.trim() !== "" ? Number(ssQuota) : null,
        }),
      }),
    onSuccess: () => {
      toast({ title: "自助領取設定已更新" });
      queryClient.invalidateQueries({ queryKey: ["admin", "catalog-models-admin"] });
    },
    onError: (e) => toast({ title: "更新失敗", description: e.message, variant: "destructive" }),
  });

  const patchMut = useMutation<unknown, ApiError, void>({
    mutationFn: () =>
      api(`/admin/catalog/models/${slug}/access`, {
        method: "PATCH",
        body: JSON.stringify({
          default_access: defaultAccess,
          allowed_tags: allowedTags,
          denied_tags: deniedTags,
        }),
      }),
    onSuccess: () => {
      toast({ title: "存取規則已更新" });
      queryClient.invalidateQueries({ queryKey: ["admin", "catalog-models-admin"] });
    },
    onError: (e) => toast({ title: "更新失敗", description: e.message, variant: "destructive" }),
  });

  // Phase 25: responses (Agent) support — test (real call) or manual override.
  const testResponsesMut = useMutation<
    { ok: boolean; latency_ms?: number; error_type?: string; message?: string },
    ApiError,
    void
  >({
    mutationFn: () =>
      api(`/admin/catalog/models/${slug}/test-responses`, { method: "POST" }),
    onSuccess: (r) => {
      if (r.ok) {
        toast({ title: "Responses 測試通過", description: `延遲 ${r.latency_ms} ms` });
      } else {
        toast({
          title: "Responses 測試未通過",
          description: r.message ?? r.error_type ?? "上游錯誤",
          variant: "destructive",
        });
      }
      queryClient.invalidateQueries({ queryKey: ["admin", "catalog-models-admin"] });
    },
    onError: (e) => toast({ title: "測試失敗", description: e.message, variant: "destructive" }),
  });

  const setSupportMut = useMutation<unknown, ApiError, boolean>({
    mutationFn: (available: boolean) =>
      api(`/admin/catalog/models/${slug}/responses-support`, {
        method: "POST",
        body: JSON.stringify({ available }),
      }),
    onSuccess: () => {
      toast({ title: "Responses 可用性已更新（手動）" });
      queryClient.invalidateQueries({ queryKey: ["admin", "catalog-models-admin"] });
    },
    onError: (e) => toast({ title: "更新失敗", description: e.message, variant: "destructive" }),
  });

  // Phase 26: test the model itself (by kind: chat/embedding/tts/image).
  const [billableConfirmOpen, setBillableConfirmOpen] = React.useState(false);
  const testModelMut = useMutation<
    { ok: boolean; kind?: string; latency_ms?: number; error_type?: string; message?: string; needs_confirmation?: boolean },
    ApiError,
    { acknowledge_billable?: boolean }
  >({
    mutationFn: (body) =>
      api(`/admin/catalog/models/${slug}/test`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: (r) => {
      if (r.needs_confirmation) {
        setBillableConfirmOpen(true);
        return;
      }
      if (r.ok) {
        toast({ title: "模型測試通過", description: `延遲 ${r.latency_ms} ms` });
      } else {
        toast({
          title: "模型測試未通過",
          description: r.message ?? r.error_type ?? "上游錯誤",
          variant: "destructive",
        });
      }
    },
    onError: (e) => toast({ title: "測試失敗", description: e.message, variant: "destructive" }),
  });

  const onTestModel = () => {
    if (model?.test_supported === false) {
      toast({ title: "尚不支援自動測試", description: "此模型類型目前無法自動測試。" });
      return;
    }
    if (model?.test_billable) {
      setBillableConfirmOpen(true);
      return;
    }
    testModelMut.mutate({});
  };

  const [editBasicsOpen, setEditBasicsOpen] = React.useState(false);
  const [checkOpen, setCheckOpen] = React.useState(false);

  const addTag = (
    list: string[],
    setList: (v: string[]) => void,
    input: string,
    setInput: (v: string) => void,
  ) => {
    const t = input.trim().toLowerCase();
    if (!t || !/^[a-z][a-z0-9_-]{0,63}$/.test(t)) {
      toast({ title: "標籤格式錯誤", variant: "destructive" });
      return;
    }
    if (!list.includes(t)) setList([...list, t]);
    setInput("");
  };

  if (modelsQuery.isLoading) {
    return <div className="container mx-auto py-8">載入中…</div>;
  }
  if (!model) {
    return (
      <div className="container mx-auto py-8 max-w-3xl space-y-4">
        <p>找不到模型「{slug}」</p>
        <Button asChild variant="outline">
          <Link to="/admin/model">回模型列表</Link>
        </Button>
      </div>
    );
  }

  const vis = model.visibility;
  return (
    <div className="container mx-auto py-8 max-w-3xl space-y-4">
      <div className="text-sm">
        <Link to="/admin/model" className="text-muted-foreground hover:underline">← 回模型</Link>
      </div>

      {/* 1. 基本資訊 */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <div>
              <CardTitle className="text-xl">{model.display_name}</CardTitle>
              <CardDescription className="font-mono text-xs">{model.slug}</CardDescription>
            </div>
            <div className="flex shrink-0 flex-wrap gap-1">
              <Button
                variant="outline"
                size="sm"
                disabled={testModelMut.isPending || model.test_supported === false}
                title={model.test_supported === false ? "此模型類型尚不支援自動測試" : undefined}
                onClick={onTestModel}
              >
                {testModelMut.isPending ? "測試中…" : "測試模型"}
              </Button>
              <Button variant="outline" size="sm" onClick={() => setCheckOpen(true)}>
                檢查 LiteLLM 更新
              </Button>
              <Button variant="outline" size="sm" onClick={() => setEditBasicsOpen(true)}>
                編輯
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
            <div><span className="text-muted-foreground">供應商：</span>{model.provider}</div>
            <div><span className="text-muted-foreground">Cost tier：</span>{model.cost_tier}</div>
            <div>
              <span className="text-muted-foreground">Context window：</span>
              {model.context_window.toLocaleString()}
              <FieldSourceBadge source={model.litellm_sync?.field_sources?.context_window} />
            </div>
            <div>
              <span className="text-muted-foreground">輸入/輸出模態：</span>
              {model.modality_input.join(", ")} / {model.modality_output.join(", ")}
              <FieldSourceBadge source={model.litellm_sync?.field_sources?.modality_input} />
            </div>
            <div className="sm:col-span-2">
              <span className="text-muted-foreground">能力：</span>
              {model.capabilities.join(", ") || "—"}
              <FieldSourceBadge source={model.litellm_sync?.field_sources?.capabilities} />
            </div>
            <div className="col-span-3">
              <span className="text-muted-foreground">價格（每 1M）：</span>
              {model.price
                ? <span className="font-mono">輸入 ${per1kToPer1m(model.price.input_per_1k)} / 輸出 ${per1kToPer1m(model.price.output_per_1k)}{model.price.cached_input_per_1k && ` / 快取輸入 $${per1kToPer1m(model.price.cached_input_per_1k)}`}</span>
                : <span className="text-amber-700">未定價</span>}
              <Link to="/admin/model/prices" className="ml-2 text-xs text-primary hover:underline">管理價目 →</Link>
            </div>
            <div className="col-span-3"><span className="text-muted-foreground">說明：</span>{model.description || "—"}</div>
          </div>
          <LiteLLMRawPanel raw={model.litellm_sync?.raw} />
        </CardContent>
      </Card>

      {checkOpen && (
        <LiteLLMUpdateDiff
          slug={model.slug}
          open={checkOpen}
          onOpenChange={setCheckOpen}
          onApplied={() => queryClient.invalidateQueries({ queryKey: ["admin", "catalog-models-admin"] })}
        />
      )}

      {/* Phase 25: Agent 相容（Responses）support */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Agent 相容（Responses）</CardTitle>
          <CardDescription>
            這個模型能不能走 <span className="font-mono">/v1/responses</span>（Codex／Agent 入口）。
            可「測試」實打一次判定，或手動指定；手動會蓋過實測。未測也未手動時，runtime 仍會先試。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2 text-sm">
            <span>目前狀態：</span>
            {(() => {
              const st = model.responses_support?.state ?? "unknown";
              const src = model.responses_support?.source;
              const label =
                st === "available" ? "可用" : st === "unavailable" ? "不可用" : "未知";
              const variant =
                st === "available" ? "default" : st === "unavailable" ? "destructive" : "outline";
              const srcLabel = src === "tested" ? "實測" : src === "manual" ? "手動" : null;
              return (
                <>
                  <Badge variant={variant as "default" | "destructive" | "outline"}>{label}</Badge>
                  {srcLabel && <span className="text-muted-foreground">來源：{srcLabel}</span>}
                </>
              );
            })()}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={testResponsesMut.isPending}
              onClick={() => testResponsesMut.mutate()}
            >
              {testResponsesMut.isPending ? "測試中…" : "測試 responses"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={setSupportMut.isPending}
              onClick={() => setSupportMut.mutate(true)}
            >
              手動設為可用
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={setSupportMut.isPending}
              onClick={() => setSupportMut.mutate(false)}
            >
              手動設為不可用
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 2. 存取規則 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">存取規則</CardTitle>
          <CardDescription>
            設定後即時生效。成員下一次呼叫目錄或 proxy 立刻看到新規則。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label>預設可見性</Label>
            <RadioGroup
              value={defaultAccess}
              onValueChange={(v) => setDefaultAccess(v as "open" | "restricted")}
              className="mt-2"
            >
              <div className="flex items-center gap-2">
                <RadioGroupItem id="da-open" value="open" />
                <Label htmlFor="da-open" className="font-normal text-sm">
                  開放 — 所有使用中的成員可見（被 denied_tags 命中者除外）
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem id="da-restricted" value="restricted" />
                <Label htmlFor="da-restricted" className="font-normal text-sm">
                  限定 — 只有命中 allowed_tags 的成員可見
                </Label>
              </div>
            </RadioGroup>
          </div>

          <TagsEditor
            label="允許標籤"
            tags={allowedTags}
            input={allowInput}
            setInput={setAllowInput}
            onAdd={() => addTag(allowedTags, setAllowedTags, allowInput, setAllowInput)}
            onRemove={(t) => setAllowedTags(allowedTags.filter((x) => x !== t))}
            variant="secondary"
          />

          <TagsEditor
            label="拒絕標籤（優先於允許）"
            tags={deniedTags}
            input={denyInput}
            setInput={setDenyInput}
            onAdd={() => addTag(deniedTags, setDeniedTags, denyInput, setDenyInput)}
            onRemove={(t) => setDeniedTags(deniedTags.filter((x) => x !== t))}
            variant="destructive"
          />

          <div className="pt-2">
            <Button onClick={() => patchMut.mutate()} disabled={patchMut.isPending}>
              {patchMut.isPending ? "套用中…" : "套用"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 2.5 自助領取 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">自助領取</CardTitle>
          <CardDescription>
            開放後，被存取規則允許的成員可在自己的儀表板一鍵領取此模型 的憑證，不需 admin 逐筆建立。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <Switch id="ss-enabled" checked={ssEnabled} onCheckedChange={setSsEnabled} />
            <Label htmlFor="ss-enabled">允許自助領取</Label>
          </div>
          {ssEnabled && (
            <div>
              <Label htmlFor="ss-quota">自助領取預設月配額 tokens（必填）</Label>
              <Input
                id="ss-quota"
                type="number"
                className="mt-1"
                placeholder="50000"
                value={ssQuota}
                onChange={(e) => setSsQuota(e.target.value)}
              />
              <p className="text-xs text-muted-foreground mt-1">
                每張自助領取的憑證以此為初始月配額；之後比照一般分配進配額池調整。
              </p>
            </div>
          )}
          <div className="pt-1">
            <Button
              variant="outline"
              onClick={() => ssMut.mutate()}
              disabled={ssMut.isPending || (ssEnabled && ssQuota.trim() === "")}
            >
              {ssMut.isPending ? "套用中…" : "套用自助設定"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 3. 健康診斷 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">健康診斷</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {vis && (
            <div className="text-sm space-y-1">
              <div>
                <span className="text-muted-foreground">供應商憑證：</span>
                {vis.provider_has_credential ? (
                  <Badge>使用中</Badge>
                ) : (
                  <Badge variant="outline" className="text-amber-700 border-amber-500">
                    ⚠ 無使用中的憑證
                  </Badge>
                )}
                {!vis.provider_has_credential && (
                  <Button asChild size="sm" variant="link" className="px-1">
                    <Link to="/admin/providers">去新增</Link>
                  </Button>
                )}
              </div>
              <div>
                <span className="text-muted-foreground">對成員可見：</span>
                <strong>{vis.visible_member_count}</strong> / {vis.total_active_members} 使用中的成員
              </div>
              <div>
                <span className="text-muted-foreground">綁定的分配：</span>
                <strong>{vis.allocation_count}</strong> 筆
              </div>
            </div>
          )}

          <VisibilityDiagnose modelSlug={slug} compact />
        </CardContent>
      </Card>

      <EditBasicsDialog
        slug={slug}
        model={editBasicsOpen ? model : null}
        onOpenChange={(open) => setEditBasicsOpen(open)}
        onSaved={() => {
          toast({ title: "基本資訊已更新" });
          queryClient.invalidateQueries({ queryKey: ["admin", "catalog-models-admin"] });
          setEditBasicsOpen(false);
        }}
      />

      <AlertDialog open={billableConfirmOpen} onOpenChange={setBillableConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>這個測試會產生實際費用</AlertDialogTitle>
            <AlertDialogDescription>
              {model.test_kind === "image"
                ? "測試圖片生成模型會實際生成一張圖片，產生一次實際費用。要繼續嗎？"
                : "測試此模型會實際呼叫上游，產生一次實際費用。要繼續嗎？"}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setBillableConfirmOpen(false);
                testModelMut.mutate({ acknowledge_billable: true });
              }}
            >
              確認測試
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function EditBasicsDialog({
  slug,
  model,
  onOpenChange,
  onSaved,
}: {
  slug: string;
  model: CatalogModel | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const { toast } = useToast();
  const [displayName, setDisplayName] = React.useState("");
  const [family, setFamily] = React.useState("");
  const [costTier, setCostTier] = React.useState("low");
  const [contextWindow, setContextWindow] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [modalityIn, setModalityIn] = React.useState("");
  const [modalityOut, setModalityOut] = React.useState("");
  const [capabilities, setCapabilities] = React.useState("");
  const [recommendedFor, setRecommendedFor] = React.useState("");
  const [tags, setTags] = React.useState("");

  React.useEffect(() => {
    if (model) {
      setDisplayName(model.display_name);
      setFamily(model.family);
      setCostTier(model.cost_tier);
      setContextWindow(String(model.context_window));
      setDescription(model.description);
      setModalityIn(model.modality_input.join(", "));
      setModalityOut(model.modality_output.join(", "));
      setCapabilities(model.capabilities.join(", "));
      setRecommendedFor(model.recommended_for.join(", "));
      setTags(model.tags.join(", "));
    }
  }, [model]);

  const csv = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

  const mut = useMutation<unknown, ApiError, void>({
    mutationFn: () =>
      api(`/admin/catalog/models/${slug}`, {
        method: "PATCH",
        body: JSON.stringify({
          display_name: displayName.trim(),
          family: family.trim(),
          cost_tier: costTier,
          context_window: Number(contextWindow),
          description: description,
          modality_input: csv(modalityIn),
          modality_output: csv(modalityOut),
          capabilities: csv(capabilities),
          recommended_for: csv(recommendedFor),
          tags: csv(tags),
        }),
      }),
    onSuccess: () => onSaved(),
    onError: (e) => toast({ title: "更新失敗", description: e.message, variant: "destructive" }),
  });

  return (
    <Dialog open={model !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>編輯基本資訊</DialogTitle>
          <DialogDescription>
            <span className="font-mono text-xs">{slug}</span>；供應商與 slug 不可改（改 slug 等於換模型）。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label htmlFor="b-name">顯示名稱</Label>
              <Input id="b-name" className="mt-1" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="b-family">Family</Label>
              <Input id="b-family" className="mt-1" value={family} onChange={(e) => setFamily(e.target.value)} />
            </div>
            <div>
              <Label>成本等級</Label>
              <Select value={costTier} onValueChange={setCostTier}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">low</SelectItem>
                  <SelectItem value="medium">medium</SelectItem>
                  <SelectItem value="high">high</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="b-ctx">Context window</Label>
              <Input id="b-ctx" type="number" className="mt-1" value={contextWindow} onChange={(e) => setContextWindow(e.target.value)} />
            </div>
          </div>
          <div>
            <Label htmlFor="b-desc">說明</Label>
            <Textarea id="b-desc" className="mt-1" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label htmlFor="b-mi">輸入模態（逗號分隔）</Label>
              <Input id="b-mi" className="mt-1" placeholder="text, image" value={modalityIn} onChange={(e) => setModalityIn(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="b-mo">輸出模態（逗號分隔）</Label>
              <Input id="b-mo" className="mt-1" placeholder="text" value={modalityOut} onChange={(e) => setModalityOut(e.target.value)} />
            </div>
          </div>
          <div>
            <Label htmlFor="b-cap">能力（逗號分隔）</Label>
            <Input id="b-cap" className="mt-1" placeholder="chat, vision, function-calling" value={capabilities} onChange={(e) => setCapabilities(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="b-rec">適用情境（逗號分隔）</Label>
            <Input id="b-rec" className="mt-1" placeholder="chat, summarization" value={recommendedFor} onChange={(e) => setRecommendedFor(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="b-tags">標籤（逗號分隔）</Label>
            <Input id="b-tags" className="mt-1" value={tags} onChange={(e) => setTags(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button disabled={!displayName.trim() || mut.isPending} onClick={() => mut.mutate()}>儲存</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function TagsEditor({
  label,
  tags,
  input,
  setInput,
  onAdd,
  onRemove,
  variant,
}: {
  label: string;
  tags: string[];
  input: string;
  setInput: (v: string) => void;
  onAdd: () => void;
  onRemove: (t: string) => void;
  variant: "secondary" | "destructive";
}) {
  return (
    <div>
      <Label>{label}</Label>
      <div className="flex gap-2 mt-1">
        <Input
          placeholder="標籤名稱"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              onAdd();
            }
          }}
        />
        <Button type="button" variant="outline" onClick={onAdd}>加入</Button>
      </div>
      <div className="flex flex-wrap gap-1 mt-2">
        {tags.length === 0 ? (
          <p className="text-xs text-muted-foreground">尚未指定</p>
        ) : (
          tags.map((t) => (
            <Badge key={t} variant={variant} className="cursor-pointer text-xs">
              {t}
              <button
                type="button"
                className="ml-1 hover:underline"
                onClick={() => onRemove(t)}
              >
                ✕
              </button>
            </Badge>
          ))
        )}
      </div>
    </div>
  );
}
