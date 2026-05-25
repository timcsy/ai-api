import * as React from "react";
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
import { ApiError, api } from "@/lib/api-client";

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

export function AdminCatalogManagePage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [createOpen, setCreateOpen] = React.useState(false);
  const [deleteConfirm, setDeleteConfirm] = React.useState<CatalogModel | null>(null);

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
        }),
      });
    },
    onSuccess: () => {
      setCreateOpen(false);
      createForm.reset();
      toast({ title: "已加入 catalog" });
      queryClient.invalidateQueries({ queryKey: ["admin", "catalog-models-admin"] });
    },
    onError: (e) => toast({ title: "新增失敗", description: e.message, variant: "destructive" }),
  });

  const deleteMut = useMutation<void, ApiError, string>({
    mutationFn: (slug) =>
      api(`/admin/catalog/models/${slug}`, { method: "DELETE" }),
    onSuccess: () => {
      toast({ title: "已從 catalog 移除" });
      setDeleteConfirm(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "catalog-models-admin"] });
    },
    onError: (e) => toast({ title: "刪除失敗", description: e.message, variant: "destructive" }),
  });

  return (
    <div className="container mx-auto py-8 max-w-6xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Catalog 管理</h1>
        <Button onClick={() => setCreateOpen(true)}>加入 Model</Button>
      </div>

      <p className="text-sm text-muted-foreground">
        這裡列出 gateway 已知的所有 model。Member 在「模型目錄」看到的會再經過
        credential gate（provider 必須有 active credential）與 access policy（tag）兩段過濾。
        若 model 對應的 provider 尚無 credential，model 仍然存在於 catalog 但對 member 隱藏。
      </p>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Slug</TableHead>
            <TableHead>顯示名稱</TableHead>
            <TableHead>Provider</TableHead>
            <TableHead>Cost Tier</TableHead>
            <TableHead>Access</TableHead>
            <TableHead>Status</TableHead>
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
              <TableCell colSpan={7} className="text-muted-foreground">
                Catalog 是空的。按「加入 Model」開始。
              </TableCell>
            </TableRow>
          )}
          {query.data?.map((m) => (
            <TableRow key={m.slug}>
              <TableCell className="font-mono text-xs">{m.slug}</TableCell>
              <TableCell>{m.display_name}</TableCell>
              <TableCell>{m.provider}</TableCell>
              <TableCell>
                <Badge variant="outline">{m.cost_tier}</Badge>
              </TableCell>
              <TableCell>
                <Badge variant={m.default_access === "open" ? "default" : "secondary"}>
                  {m.default_access}
                </Badge>
                {(m.allowed_tags.length > 0 || m.denied_tags.length > 0) && (
                  <span className="ml-1 text-xs text-muted-foreground">
                    +{m.allowed_tags.length}/-{m.denied_tags.length}
                  </span>
                )}
              </TableCell>
              <TableCell>
                {m.status === "active" ? (
                  <Badge>active</Badge>
                ) : (
                  <Badge variant="secondary">{m.status}</Badge>
                )}
              </TableCell>
              <TableCell className="text-right">
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => setDeleteConfirm(m)}
                >
                  移除
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>加入 Model 到 Catalog</DialogTitle>
            <DialogDescription>
              對 Azure：Model 名稱填你的 <strong>deployment 名稱</strong>（不是 OpenAI 公版的名稱）。
              對 OpenAI / Anthropic / Gemini：填官方 model id（例：claude-3-5-sonnet-20241022）。
            </DialogDescription>
          </DialogHeader>
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
                    <FormLabel>Provider</FormLabel>
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
                    <FormLabel>Model / Deployment 名稱</FormLabel>
                    <FormControl>
                      <Input placeholder="例：gpt-5.4-mini" {...field} />
                    </FormControl>
                    <p className="text-xs text-muted-foreground mt-1">
                      <strong>Azure</strong>：填你的 deployment 名稱（不是 OpenAI 公版名稱；每個訂閱不同）。<br />
                      <strong>OpenAI / Anthropic / Gemini</strong>：填官方 model id（例：
                      <code>claude-3-5-sonnet-20241022</code>、<code>gpt-4o-mini</code>、
                      <code>gemini-1.5-flash</code>）。
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

      <AlertDialog
        open={deleteConfirm !== null}
        onOpenChange={(v) => !v && setDeleteConfirm(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>從 catalog 移除？</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteConfirm && (
                <code className="text-xs">{deleteConfirm.slug}</code>
              )}
              <span className="block mt-2">
                移除後 member 將看不到、也呼叫不到此 model。既有 allocation 若綁定此 model 仍存在但會 503。
              </span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteConfirm && deleteMut.mutate(deleteConfirm.slug)}
            >
              移除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
