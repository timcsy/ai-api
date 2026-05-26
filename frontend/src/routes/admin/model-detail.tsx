import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  RadioGroup,
  RadioGroupItem,
} from "@/components/ui/radio-group";
import { useToast } from "@/components/ui/use-toast";
import { VisibilityDiagnose } from "@/components/visibility-diagnose";
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
  description: string;
  context_window: number;
  cost_tier: string;
  status: string;
  default_access: "open" | "restricted";
  allowed_tags: string[];
  denied_tags: string[];
  visibility?: Visibility;
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
  const seededRef = React.useRef(false);
  React.useEffect(() => {
    if (model && !seededRef.current) {
      setDefaultAccess(model.default_access);
      setAllowedTags([...model.allowed_tags]);
      setDeniedTags([...model.denied_tags]);
      seededRef.current = true;
    }
  }, [model]);

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

  const addTag = (
    list: string[],
    setList: (v: string[]) => void,
    input: string,
    setInput: (v: string) => void,
  ) => {
    const t = input.trim().toLowerCase();
    if (!t || !/^[a-z][a-z0-9_-]{0,63}$/.test(t)) {
      toast({ title: "Tag 格式錯誤", variant: "destructive" });
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
        <p>找不到 model「{slug}」</p>
        <Button asChild variant="outline">
          <Link to="/admin/model">回 Model 列表</Link>
        </Button>
      </div>
    );
  }

  const vis = model.visibility;
  return (
    <div className="container mx-auto py-8 max-w-3xl space-y-4">
      <div className="text-sm">
        <Link to="/admin/model" className="text-muted-foreground hover:underline">← 回 Model</Link>
      </div>

      {/* 1. 基本資訊 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">{model.display_name}</CardTitle>
          <CardDescription className="font-mono text-xs">{model.slug}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-3 text-sm">
            <div><span className="text-muted-foreground">Provider：</span>{model.provider}</div>
            <div><span className="text-muted-foreground">Cost tier：</span>{model.cost_tier}</div>
            <div><span className="text-muted-foreground">Context window：</span>{model.context_window.toLocaleString()}</div>
            <div className="col-span-3"><span className="text-muted-foreground">說明：</span>{model.description || "—"}</div>
          </div>
        </CardContent>
      </Card>

      {/* 2. 存取規則 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">存取規則</CardTitle>
          <CardDescription>
            設定後即時生效。member 下一次呼叫 catalog 或 proxy 立刻看到新規則。
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
                  open — 所有 active member 可見（被 denied_tags 命中者除外）
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem id="da-restricted" value="restricted" />
                <Label htmlFor="da-restricted" className="font-normal text-sm">
                  restricted — 只有命中 allowed_tags 的 member 可見
                </Label>
              </div>
            </RadioGroup>
          </div>

          <TagsEditor
            label="Allowed Tags"
            tags={allowedTags}
            input={allowInput}
            setInput={setAllowInput}
            onAdd={() => addTag(allowedTags, setAllowedTags, allowInput, setAllowInput)}
            onRemove={(t) => setAllowedTags(allowedTags.filter((x) => x !== t))}
            variant="secondary"
          />

          <TagsEditor
            label="Denied Tags（優先於 Allowed）"
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

      {/* 3. 健康診斷 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">健康診斷</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {vis && (
            <div className="text-sm space-y-1">
              <div>
                <span className="text-muted-foreground">Provider credential：</span>
                {vis.provider_has_credential ? (
                  <Badge>active</Badge>
                ) : (
                  <Badge variant="outline" className="text-amber-700 border-amber-500">
                    ⚠ 無 active credential
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
                <strong>{vis.visible_member_count}</strong> / {vis.total_active_members} active member
              </div>
              <div>
                <span className="text-muted-foreground">綁定的 allocation：</span>
                <strong>{vis.allocation_count}</strong> 筆
              </div>
            </div>
          )}

          <VisibilityDiagnose modelSlug={slug} compact />
        </CardContent>
      </Card>
    </div>
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
          placeholder="tag 名稱"
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
