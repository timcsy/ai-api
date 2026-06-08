import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { ApiError, api } from "@/lib/api-client";

interface VisibilityCheck {
  check: "credential_gate" | "default_access" | "deny_tags" | "allow_tags";
  pass: boolean;
  detail: string;
}

interface VisibilityResult {
  visible: boolean;
  reason_chain: VisibilityCheck[];
}

interface AdminMember {
  id: string;
  email: string;
  status: string;
}

interface CatalogModel {
  slug: string;
  display_name: string;
  provider: string;
  allowed_tags?: string[];
}

interface Props {
  /** Pre-fill model side; member side becomes picker */
  modelSlug?: string;
  /** Pre-fill member side; model side becomes picker */
  memberId?: string;
  /** Compact mode for embedding inside a card */
  compact?: boolean;
}

const CHECK_LABEL: Record<VisibilityCheck["check"], string> = {
  credential_gate: "Provider 憑證",
  default_access: "預設可見性",
  deny_tags: "拒絕標籤規則",
  allow_tags: "允許標籤規則",
};

export function VisibilityDiagnose({ modelSlug, memberId, compact = false }: Props) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [selectedMember, setSelectedMember] = React.useState(memberId ?? "");
  const [selectedModel, setSelectedModel] = React.useState(modelSlug ?? "");

  const members = useQuery<AdminMember[], ApiError>({
    queryKey: ["admin", "members"],
    queryFn: () => api<AdminMember[]>("/admin/members"),
    enabled: !memberId,
  });
  const models = useQuery<CatalogModel[], ApiError>({
    queryKey: ["admin", "catalog-models-admin"],
    queryFn: () => api<CatalogModel[]>("/admin/catalog/models"),
    enabled: !modelSlug,
  });
  // Always fetch the chosen model to know its allowed_tags for repair hints
  const modelMeta = useQuery<CatalogModel[], ApiError>({
    queryKey: ["admin", "catalog-models-admin", "all"],
    queryFn: () => api<CatalogModel[]>("/admin/catalog/models"),
  });

  const enabled = !!(selectedMember && selectedModel);
  const result = useQuery<VisibilityResult, ApiError>({
    queryKey: ["admin", "diagnose", selectedMember, selectedModel],
    queryFn: () =>
      api<VisibilityResult>(
        `/admin/diagnose/visibility?member_id=${encodeURIComponent(selectedMember)}&model_slug=${encodeURIComponent(selectedModel)}`,
      ),
    enabled,
  });

  const currentModel = React.useMemo(
    () => modelMeta.data?.find((m) => m.slug === selectedModel),
    [modelMeta.data, selectedModel],
  );

  const addTagMut = useMutation<unknown, ApiError, string>({
    mutationFn: (tag) =>
      api(`/admin/members/${selectedMember}/tags`, {
        method: "POST",
        body: JSON.stringify({ tags: [tag] }),
      }),
    onSuccess: (_, tag) => {
      toast({ title: `已給該成員加標籤「${tag}」` });
      queryClient.invalidateQueries({ queryKey: ["admin", "diagnose"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "members", selectedMember, "tags"] });
    },
    onError: (e) => toast({ title: "加標籤失敗", description: e.message, variant: "destructive" }),
  });

  const removeTagMut = useMutation<void, ApiError, string>({
    mutationFn: (tag) =>
      api<void>(`/admin/members/${selectedMember}/tags?tag=${encodeURIComponent(tag)}`, {
        method: "DELETE",
      }),
    onSuccess: (_, tag) => {
      toast({ title: `已移除標籤「${tag}」` });
      queryClient.invalidateQueries({ queryKey: ["admin", "diagnose"] });
    },
    onError: (e) => toast({ title: "移除失敗", description: e.message, variant: "destructive" }),
  });

  return (
    <Card>
      <CardHeader className={compact ? "pb-3" : undefined}>
        <CardTitle className="text-base">以指定 member 視角預覽</CardTitle>
        <CardDescription>
          評估 (成員, 模型) 兩段過濾，告訴你「可見 / 不可見 + 原因」並提供修補捷徑。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          {!memberId && (
            <div>
              <Select value={selectedMember} onValueChange={setSelectedMember}>
                <SelectTrigger><SelectValue placeholder="選成員" /></SelectTrigger>
                <SelectContent>
                  {members.data?.map((m) => (
                    <SelectItem key={m.id} value={m.id}>{m.email}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          {!modelSlug && (
            <div>
              <Select value={selectedModel} onValueChange={setSelectedModel}>
                <SelectTrigger><SelectValue placeholder="選模型" /></SelectTrigger>
                <SelectContent>
                  {models.data?.map((m) => (
                    <SelectItem key={m.slug} value={m.slug}>{m.slug}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>

        {!enabled && (
          <p className="text-xs text-muted-foreground">兩邊都選後即時評估。</p>
        )}

        {result.isLoading && enabled && <p className="text-sm">評估中…</p>}

        {result.data && (
          <div className="space-y-2">
            <div>
              <Badge variant={result.data.visible ? "default" : "outline"} className={result.data.visible ? "" : "text-amber-700 border-amber-500"}>
                {result.data.visible ? "✓ 可見" : "✗ 不可見"}
              </Badge>
            </div>
            <ol className="text-xs space-y-1">
              {result.data.reason_chain.map((check, i) => (
                <li key={i} className="flex items-start gap-2 border-l-2 pl-2 border-muted">
                  <span className="font-mono">{check.pass ? "✓" : "✗"}</span>
                  <div className="flex-1">
                    <div className="font-medium">{CHECK_LABEL[check.check]}</div>
                    <div className="text-muted-foreground">{check.detail}</div>
                    {!check.pass && (
                      <RepairCta
                        check={check.check}
                        allowedTags={currentModel?.allowed_tags ?? []}
                        onAddTag={(t) => addTagMut.mutate(t)}
                        onRemoveTag={(t) => removeTagMut.mutate(t)}
                      />
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RepairCta({
  check,
  allowedTags,
  onAddTag,
}: {
  check: VisibilityCheck["check"];
  allowedTags: string[];
  onAddTag: (tag: string) => void;
  onRemoveTag: (tag: string) => void;
}) {
  if (check === "credential_gate") {
    return (
      <Button asChild size="sm" variant="outline" className="mt-1">
        <Link to="/admin/providers">去新增該 provider 的 credential</Link>
      </Button>
    );
  }
  if (check === "allow_tags") {
    if (allowedTags.length === 0) {
      return (
        <p className="text-muted-foreground mt-1">
          此模型設為 restricted 但 allowed_tags 是空的；需到「模型存取」設定。
        </p>
      );
    }
    return (
      <div className="flex flex-wrap gap-1 mt-1">
        {allowedTags.map((t) => (
          <Button
            key={t}
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            onClick={() => onAddTag(t)}
          >
            給該成員加標籤「{t}」
          </Button>
        ))}
      </div>
    );
  }
  if (check === "deny_tags") {
    // The check.detail includes which tags hit. We don't parse it; just hint.
    return (
      <p className="text-muted-foreground mt-1">
        要解除，需移除該成員命中 denied_tags 的標籤（去成員頁編輯）。
      </p>
    );
  }
  return null;
}
