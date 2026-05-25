import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { useToast } from "@/components/ui/use-toast";
import { ApiError, api } from "@/lib/api-client";

interface CatalogModel {
  slug: string;
  display_name: string;
  provider: string;
}

interface AccessPolicy {
  slug: string;
  default_access: "open" | "restricted";
  allowed_tags: string[];
  denied_tags: string[];
}

interface TagSummary {
  tag: string;
  member_count: number;
}

export function AdminModelAccessPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [selectedSlug, setSelectedSlug] = React.useState<string>("");

  const modelsQuery = useQuery<CatalogModel[], ApiError>({
    queryKey: ["admin", "catalog-models-for-access"],
    queryFn: () => api<CatalogModel[]>("/catalog/models?include_deprecated=true"),
  });

  const tagsQuery = useQuery<TagSummary[], ApiError>({
    queryKey: ["admin", "tags"],
    queryFn: () => api<TagSummary[]>("/admin/tags"),
  });

  // current policy is read from catalog model row; admin endpoints don't expose
  // a GET for policy, but we can derive from /catalog/models/{slug} for active
  // models. For now we manage local state, seeded on slug change.
  const [defaultAccess, setDefaultAccess] = React.useState<"open" | "restricted">("open");
  const [allowedTags, setAllowedTags] = React.useState<string[]>([]);
  const [deniedTags, setDeniedTags] = React.useState<string[]>([]);
  const [allowInput, setAllowInput] = React.useState("");
  const [denyInput, setDenyInput] = React.useState("");

  const patchMut = useMutation<AccessPolicy, ApiError, AccessPolicy>({
    mutationFn: (data) =>
      api(`/admin/catalog/models/${data.slug}/access`, {
        method: "PATCH",
        body: JSON.stringify({
          default_access: data.default_access,
          allowed_tags: data.allowed_tags,
          denied_tags: data.denied_tags,
        }),
      }),
    onSuccess: (snap) => {
      toast({
        title: `已更新 ${snap.slug} 的存取政策`,
        description: `${snap.default_access} / allow=${snap.allowed_tags.length} / deny=${snap.denied_tags.length}`,
      });
      queryClient.invalidateQueries({ queryKey: ["admin", "catalog-models-for-access"] });
    },
    onError: (e) => toast({ title: "更新失敗", description: e.message, variant: "destructive" }),
  });

  const addTag = (list: string[], setList: (v: string[]) => void, input: string, setInput: (v: string) => void) => {
    const t = input.trim().toLowerCase();
    if (!t) return;
    if (!/^[a-z][a-z0-9_-]{0,63}$/.test(t)) {
      toast({ title: "Tag 格式錯誤", description: "^[a-z][a-z0-9_-]{0,63}$", variant: "destructive" });
      return;
    }
    if (list.includes(t)) return;
    setList([...list, t]);
    setInput("");
  };

  return (
    <div className="container mx-auto py-8 max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Model 存取規則</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">選擇 Model</CardTitle>
          <CardDescription>
            設定後即時生效；成員下一次呼叫 catalog 或 proxy 立刻看到新規則。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Select
            value={selectedSlug}
            onValueChange={(v) => {
              setSelectedSlug(v);
              // Reset edits — admin must explicitly set; system has no default.
              setDefaultAccess("open");
              setAllowedTags([]);
              setDeniedTags([]);
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder={modelsQuery.isLoading ? "載入中…" : "選一個 model"} />
            </SelectTrigger>
            <SelectContent>
              {modelsQuery.data?.map((m) => (
                <SelectItem key={m.slug} value={m.slug}>
                  {m.slug} <span className="text-muted-foreground ml-1">({m.provider})</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      {selectedSlug && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">存取政策</CardTitle>
            <CardDescription className="break-all">
              <code>{selectedSlug}</code>
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div>
              <Label>預設可見性</Label>
              <RadioGroup
                value={defaultAccess}
                onValueChange={(v) => setDefaultAccess(v as "open" | "restricted")}
                className="mt-2"
              >
                <div className="flex items-center gap-2">
                  <RadioGroupItem id="da-open" value="open" />
                  <Label htmlFor="da-open" className="font-normal">
                    open — 所有 active member 可見（被 denied_tags 命中者除外）
                  </Label>
                </div>
                <div className="flex items-center gap-2">
                  <RadioGroupItem id="da-restricted" value="restricted" />
                  <Label htmlFor="da-restricted" className="font-normal">
                    restricted — 只有命中 allowed_tags 的 member 可見
                  </Label>
                </div>
              </RadioGroup>
            </div>

            <div>
              <Label>Allowed Tags</Label>
              <div className="flex gap-2 mt-1">
                <Input
                  placeholder="tag 名稱"
                  value={allowInput}
                  onChange={(e) => setAllowInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addTag(allowedTags, setAllowedTags, allowInput, setAllowInput);
                    }
                  }}
                />
                <Button
                  type="button"
                  onClick={() => addTag(allowedTags, setAllowedTags, allowInput, setAllowInput)}
                >
                  加入
                </Button>
              </div>
              <div className="flex flex-wrap gap-1 mt-2">
                {allowedTags.map((t) => (
                  <Badge key={t} variant="secondary" className="cursor-pointer">
                    {t}
                    <button
                      type="button"
                      className="ml-1 hover:text-destructive"
                      onClick={() => setAllowedTags(allowedTags.filter((x) => x !== t))}
                    >
                      ✕
                    </button>
                  </Badge>
                ))}
                {allowedTags.length === 0 && (
                  <p className="text-xs text-muted-foreground">尚未指定</p>
                )}
              </div>
              {tagsQuery.data && tagsQuery.data.length > 0 && (
                <p className="text-xs text-muted-foreground mt-1">
                  既有 tag：{tagsQuery.data.map((t) => t.tag).join(", ")}
                </p>
              )}
            </div>

            <div>
              <Label>Denied Tags（優先於 Allowed）</Label>
              <div className="flex gap-2 mt-1">
                <Input
                  placeholder="tag 名稱"
                  value={denyInput}
                  onChange={(e) => setDenyInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addTag(deniedTags, setDeniedTags, denyInput, setDenyInput);
                    }
                  }}
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => addTag(deniedTags, setDeniedTags, denyInput, setDenyInput)}
                >
                  加入
                </Button>
              </div>
              <div className="flex flex-wrap gap-1 mt-2">
                {deniedTags.map((t) => (
                  <Badge key={t} variant="destructive" className="cursor-pointer">
                    {t}
                    <button
                      type="button"
                      className="ml-1 hover:underline"
                      onClick={() => setDeniedTags(deniedTags.filter((x) => x !== t))}
                    >
                      ✕
                    </button>
                  </Badge>
                ))}
                {deniedTags.length === 0 && (
                  <p className="text-xs text-muted-foreground">尚未指定</p>
                )}
              </div>
            </div>

            <Button
              disabled={patchMut.isPending}
              onClick={() =>
                patchMut.mutate({
                  slug: selectedSlug,
                  default_access: defaultAccess,
                  allowed_tags: allowedTags,
                  denied_tags: deniedTags,
                })
              }
            >
              {patchMut.isPending ? "套用中…" : "套用"}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
