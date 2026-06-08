import * as React from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { LiteLLMModelPicker, type LitellmDraft } from "@/components/litellm-model-picker";
import { ApiError, api } from "@/lib/api-client";
import { statusLabel } from "@/lib/status-label";

interface CatalogModel {
  slug: string;
  provider: string;
  display_name: string;
  family: string;
  description: string;
  context_window: number;
  cost_tier: string;
  capabilities: string[];
  status: string;
  default_access: "open" | "restricted";
  allowed_tags: string[];
  denied_tags: string[];
  visibility?: {
    provider_has_credential: boolean;
    visible_member_count: number;
    total_active_members: number;
    allocation_count: number;
  };
}

interface Dependents {
  slug: string;
  allocation_count: number;
  allocations: Array<{
    id: string;
    subject_snapshot: string;
    status: string;
  }>;
}

const PROVIDERS = ["azure", "openai", "anthropic", "gemini"] as const;

const createSchema = z.object({
  provider: z.enum(PROVIDERS),
  model_name: z.string().min(1, "必填，例如 azure 是 deployment name，openai 是 gpt-4o-mini"),
  display_name: z.string().min(1),
  description: z.string().optional(),
  context_window: z.coerce.number().int().nonnegative(),
  cost_tier: z.enum(["low", "medium", "high"]),
});

type CreateForm = z.infer<typeof createSchema>;

function DeleteWithDependentsDialog({
  target,
  onCancel,
  onConfirm,
}: {
  target: CatalogModel | null;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const depQuery = useQuery<Dependents, ApiError>({
    queryKey: ["admin", "catalog-model-dependents", target?.slug],
    queryFn: () =>
      api<Dependents>(`/admin/catalog/models/${target!.slug}/dependents`),
    enabled: target !== null,
  });
  return (
    <AlertDialog open={target !== null} onOpenChange={(v) => !v && onCancel()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>從目錄移除？</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-2">
              {target && <code className="text-xs">{target.slug}</code>}
              {depQuery.isLoading && <p className="text-xs">檢查依賴中…</p>}
              {depQuery.data && depQuery.data.allocation_count > 0 ? (
                <div className="rounded-md border border-destructive bg-destructive/10 p-2 text-xs space-y-1">
                  <p className="font-semibold">
                    ⚠ {depQuery.data.allocation_count} 筆分配依賴此模型；
                    移除後它們的呼叫會回 503 provider_unavailable。
                  </p>
                  <ul className="list-disc pl-4">
                    {depQuery.data.allocations.slice(0, 5).map((a) => (
                      <li key={a.id}>
                        {a.subject_snapshot} <span className="text-muted-foreground">({a.status})</span>
                      </li>
                    ))}
                    {depQuery.data.allocation_count > 5 && (
                      <li className="text-muted-foreground">
                        … 還有 {depQuery.data.allocation_count - 5} 筆
                      </li>
                    )}
                  </ul>
                </div>
              ) : (
                depQuery.data && (
                  <p className="text-xs text-muted-foreground">無分配依賴此模型。</p>
                )
              )}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>取消</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm}>確定移除</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export function AdminCatalogManagePage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [createOpen, setCreateOpen] = React.useState(false);
  const [deleteConfirm, setDeleteConfirm] = React.useState<CatalogModel | null>(null);
  // Phase 23: when a LiteLLM model is picked, its metadata + suggested price ride
  // along to the create POST so the backend records provenance + seeds the price.
  const [litellmDraft, setLitellmDraft] = React.useState<LitellmDraft | null>(null);

  const query = useQuery<CatalogModel[], ApiError>({
    queryKey: ["admin", "catalog-models-admin"],
    queryFn: () => api<CatalogModel[]>("/admin/catalog/models"),
  });

  const createForm = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      provider: "azure",
      model_name: "",
      display_name: "",
      description: "",
      context_window: 4096,
      cost_tier: "medium",
    },
  });

  const createMut = useMutation<CatalogModel, ApiError, CreateForm>({
    mutationFn: (data) => {
      const slug = `${data.provider}/${data.model_name}`;
      return api<CatalogModel>("/admin/catalog/models", {
        method: "POST",
        body: JSON.stringify({
          slug,
          provider: data.provider,
          display_name: data.display_name,
          description: data.description || "",
          context_window: data.context_window,
          cost_tier: data.cost_tier,
          // Phase 23: align with the picked LiteLLM model (provenance + metadata + price).
          ...(litellmDraft
            ? {
                base_model_key: litellmDraft.key,
                modality_input: litellmDraft.metadata.modality_input,
                modality_output: litellmDraft.metadata.modality_output,
                capabilities: litellmDraft.metadata.capabilities,
                suggested_price: litellmDraft.suggested_price,
              }
            : {}),
        }),
      });
    },
    onSuccess: () => {
      setCreateOpen(false);
      createForm.reset();
      setLitellmDraft(null);
      toast({ title: "已加入目錄" });
      queryClient.invalidateQueries({ queryKey: ["admin", "catalog-models-admin"] });
    },
    onError: (e) => toast({ title: "新增失敗", description: e.message, variant: "destructive" }),
  });

  const deleteMut = useMutation<void, ApiError, string>({
    mutationFn: (slug) =>
      api(`/admin/catalog/models/${slug}`, { method: "DELETE" }),
    onSuccess: () => {
      toast({ title: "已從目錄移除" });
      setDeleteConfirm(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "catalog-models-admin"] });
    },
    onError: (e) => toast({ title: "刪除失敗", description: e.message, variant: "destructive" }),
  });

  return (
    <div className="container mx-auto py-8 max-w-6xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">目錄管理</h1>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link to="/admin/model/prices">價目</Link>
          </Button>
          <Button onClick={() => setCreateOpen(true)}>加入模型</Button>
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        這裡列出本平台已知的所有模型。成員在「模型目錄」看到的會再經過
        credential gate（供應商必須有使用中的憑證）與 access policy（標籤）兩段過濾。
        若模型對應的供應商尚無憑證，模型仍然存在於目錄但對成員隱藏。
      </p>

      <Table className="responsive-table">
        <TableHeader>
          <TableRow>
            <TableHead>Slug</TableHead>
            <TableHead>顯示名稱</TableHead>
            <TableHead>供應商</TableHead>
            <TableHead>成本</TableHead>
            <TableHead>存取</TableHead>
            <TableHead>對成員可見</TableHead>
            <TableHead>狀態</TableHead>
            <TableHead className="text-right">動作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {query.isLoading && (
            <TableRow>
              <TableCell colSpan={7} className="text-muted-foreground">載入中…</TableCell>
            </TableRow>
          )}
          {query.data?.length === 0 && (
            <TableRow>
              <TableCell colSpan={8} className="text-muted-foreground">
                目錄是空的。按「加入模型」開始。
              </TableCell>
            </TableRow>
          )}
          {query.data?.map((m) => {
            const vis = m.visibility;
            const hidden = vis && vis.visible_member_count === 0;
            return (
            <TableRow key={m.slug}>
              <TableCell className="font-mono text-xs" data-label="Slug">
                <Link to={`/admin/model/${m.slug}`} className="block max-w-[180px] truncate text-primary hover:underline">
                  {m.slug}
                </Link>
              </TableCell>
              <TableCell data-label="顯示名稱">{m.display_name}</TableCell>
              <TableCell data-label="供應商">{m.provider}</TableCell>
              <TableCell data-label="成本">
                <Badge variant="outline">{m.cost_tier}</Badge>
              </TableCell>
              <TableCell data-label="存取">
                <Badge variant={m.default_access === "open" ? "default" : "secondary"}>
                  {m.default_access}
                </Badge>
                {(m.allowed_tags.length > 0 || m.denied_tags.length > 0) && (
                  <span className="ml-1 text-xs text-muted-foreground">
                    +{m.allowed_tags.length}/-{m.denied_tags.length}
                  </span>
                )}
              </TableCell>
              <TableCell data-label="對成員可見">
                {!vis ? (
                  <span className="text-xs text-muted-foreground">—</span>
                ) : !vis.provider_has_credential ? (
                  <Badge variant="outline" className="text-amber-700 border-amber-500">
                    ⚠ 無憑證
                  </Badge>
                ) : hidden ? (
                  <Badge variant="outline" className="text-amber-700 border-amber-500">
                    ⚠ 0 / {vis.total_active_members}
                  </Badge>
                ) : (
                  <Badge variant="default">
                    {vis.visible_member_count} / {vis.total_active_members}
                  </Badge>
                )}
              </TableCell>
              <TableCell data-label="狀態">
                {m.status === "active" ? (
                  <Badge>{statusLabel(m.status)}</Badge>
                ) : (
                  <Badge variant="secondary">{statusLabel(m.status)}</Badge>
                )}
              </TableCell>
              <TableCell className="text-right" data-label="動作">
                <Button size="sm" variant="destructive" onClick={() => setDeleteConfirm(m)}>
                  移除
                </Button>
              </TableCell>
            </TableRow>
          );})}
        </TableBody>
      </Table>

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>加入模型到目錄</DialogTitle>
            <DialogDescription>
              先用「從 LiteLLM 帶入」搜尋帶入，或手動填寫。
            </DialogDescription>
          </DialogHeader>
          <LiteLLMModelPicker
            onPick={(draft) => {
              setLitellmDraft(draft);
              const [, ...rest] = draft.key.split("/");
              createForm.setValue("model_name", rest.join("/") || draft.key);
              createForm.setValue("context_window", draft.metadata.context_window);
              const prov = draft.key.split("/")[0];
              if (prov && (PROVIDERS as readonly string[]).includes(prov)) {
                createForm.setValue("provider", prov as CreateForm["provider"]);
              }
            }}
          />
          {litellmDraft && (
            <p className="text-xs text-muted-foreground">
              已帶入 <span className="font-mono">{litellmDraft.key}</span>
              （context {litellmDraft.metadata.context_window.toLocaleString()}
              {litellmDraft.suggested_price ? ` · 建議價 $${litellmDraft.suggested_price.input_per_1k}/1k` : ""}）。
              可改模型名稱做自訂 deployment。
            </p>
          )}
          <Form {...createForm}>
            <form
              onSubmit={createForm.handleSubmit((d) => createMut.mutate(d))}
              className="space-y-4"
            >
              <FormField
                control={createForm.control}
                name="provider"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>供應商</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {PROVIDERS.map((p) => (
                          <SelectItem key={p} value={p}>{p}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createForm.control}
                name="model_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>模型 / Deployment 名稱</FormLabel>
                    <FormControl>
                      <Input placeholder="例：gpt-5.4-mini" {...field} />
                    </FormControl>
                    <p className="text-xs text-muted-foreground mt-1">
                      Azure 填你的 deployment 名稱；其他供應商填官方 model id。
                    </p>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createForm.control}
                name="display_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>顯示名稱</FormLabel>
                    <FormControl>
                      <Input placeholder="GPT-5.4 mini（Azure 部署）" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createForm.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>說明（選填）</FormLabel>
                    <FormControl>
                      <Textarea rows={3} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={createForm.control}
                  name="context_window"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Context Window</FormLabel>
                      <FormControl>
                        <Input type="number" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={createForm.control}
                  name="cost_tier"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Cost Tier</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="low">low</SelectItem>
                          <SelectItem value="medium">medium</SelectItem>
                          <SelectItem value="high">high</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
                  取消
                </Button>
                <Button type="submit" disabled={createMut.isPending}>
                  {createMut.isPending ? "加入中…" : "加入"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <DeleteWithDependentsDialog
        target={deleteConfirm}
        onCancel={() => setDeleteConfirm(null)}
        onConfirm={() => deleteConfirm && deleteMut.mutate(deleteConfirm.slug)}
      />
    </div>
  );
}
