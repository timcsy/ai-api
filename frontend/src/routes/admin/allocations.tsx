import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { MoreHorizontal } from "lucide-react";
import { z } from "zod";

import { Alert, AlertDescription } from "@/components/ui/alert";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/use-toast";
import { copyToClipboard } from "@/lib/clipboard";
import { ApiError, api } from "@/lib/api-client";

interface AdminAllocation {
  id: string;
  member_id: string;
  subject_snapshot: string;
  resource_model: string;
  status: string;
  quota_tokens_per_month: number | null;
  is_service_allocation: boolean;
  quota_locked: boolean;
  token_prefix: string;
  created_at: string;
}

interface AdminMember {
  id: string;
  email: string;
}

const createSchema = z.object({
  member_id: z.string().min(1),
  resource_model: z.string().min(1),
  quota_tokens_per_month: z.coerce.number().int().min(0).optional(),
  is_service_allocation: z.boolean().default(false),
  note: z.string().optional(),
});
type CreateForm = z.infer<typeof createSchema>;

export function AdminAllocationsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [createOpen, setCreateOpen] = React.useState(false);
  const [tokenDialog, setTokenDialog] = React.useState<string | null>(null);
  const [serviceOnly, setServiceOnly] = React.useState(false);

  const allocsQuery = useQuery<AdminAllocation[], ApiError>({
    queryKey: ["admin", "allocations"],
    queryFn: () => api<AdminAllocation[]>("/admin/allocations"),
  });
  const membersQuery = useQuery<AdminMember[], ApiError>({
    queryKey: ["admin", "members"],
    queryFn: () => api<AdminMember[]>("/admin/members"),
  });
  // Pull catalog slugs to detect orphan allocations (resource_model not in catalog)
  const catalogSlugs = useQuery<Array<{ slug: string }>, ApiError>({
    queryKey: ["admin", "catalog-models-admin"],
    queryFn: () => api<Array<{ slug: string }>>("/admin/catalog/models"),
  });
  const knownSlugs = React.useMemo(
    () => new Set((catalogSlugs.data ?? []).map((m) => m.slug)),
    [catalogSlugs.data],
  );

  const memberById = React.useMemo(() => {
    const map = new Map<string, AdminMember>();
    (membersQuery.data ?? []).forEach((m) => map.set(m.id, m));
    return map;
  }, [membersQuery.data]);

  const patchMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api(`/admin/allocations/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "allocations"] }),
  });
  const revokeMut = useMutation({
    mutationFn: (id: string) => api(`/admin/allocations/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "allocations"] });
      toast({ title: "已撤回" });
    },
  });

  const filtered = (allocsQuery.data ?? []).filter(
    (a) => !serviceOnly || a.is_service_allocation,
  );

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">分配管理</h1>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Switch
              id="service-only"
              checked={serviceOnly}
              onCheckedChange={setServiceOnly}
            />
            <Label htmlFor="service-only" className="text-sm">只看服務型</Label>
          </div>
          <Button onClick={() => setCreateOpen(true)}>新增分配</Button>
        </div>
      </div>

      {allocsQuery.isLoading && <p className="text-muted-foreground">載入中…</p>}
      {allocsQuery.error && (
        <Alert variant="destructive">
          <AlertDescription>無法載入：{allocsQuery.error.message}</AlertDescription>
        </Alert>
      )}

      {allocsQuery.data && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>成員</TableHead>
              <TableHead>模型</TableHead>
              <TableHead>狀態</TableHead>
              <TableHead>配額</TableHead>
              <TableHead>標籤</TableHead>
              <TableHead>Token 前綴</TableHead>
              <TableHead className="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((a) => (
              <TableRow key={a.id}>
                <TableCell className="font-medium">
                  {memberById.get(a.member_id)?.email ?? a.subject_snapshot}
                </TableCell>
                <TableCell>
                  <span className="font-mono text-xs">{a.resource_model}</span>
                  {catalogSlugs.data && !knownSlugs.has(a.resource_model) && (
                    <Badge variant="outline" className="ml-2 text-amber-700 border-amber-500">
                      ⚠ 已不在 catalog
                    </Badge>
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant={a.status === "active" ? "default" : "secondary"}>
                    {a.status}
                  </Badge>
                </TableCell>
                <TableCell>{a.quota_tokens_per_month ?? "無限額"}</TableCell>
                <TableCell className="space-x-1">
                  {a.is_service_allocation && <Badge variant="outline">service</Badge>}
                  {a.quota_locked && <Badge variant="outline">locked</Badge>}
                </TableCell>
                <TableCell className="font-mono text-xs">{a.token_prefix}…</TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() => {
                          const next = prompt("新 quota (空白=無限額)", String(a.quota_tokens_per_month ?? ""));
                          if (next === null) return;
                          const value = next.trim() === "" ? null : Number(next);
                          patchMut.mutate({ id: a.id, body: { quota_tokens_per_month: value } });
                        }}
                      >
                        調整配額
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() =>
                          patchMut.mutate({ id: a.id, body: { quota_locked: !a.quota_locked } })
                        }
                      >
                        切換鎖定配額
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() =>
                          patchMut.mutate({
                            id: a.id,
                            body: { is_service_allocation: !a.is_service_allocation },
                          })
                        }
                      >
                        切換服務型
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => {
                          if (confirm(`撤回 ${a.token_prefix}… ？`)) revokeMut.mutate(a.id);
                        }}
                      >
                        撤回
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  尚無 allocation
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}

      <CreateAllocationDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        members={membersQuery.data ?? []}
        onCreated={(token) => setTokenDialog(token)}
      />

      <Dialog open={!!tokenDialog} onOpenChange={(open) => !open && setTokenDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>分配已建立 — 此 token 只顯示一次</DialogTitle>
            <DialogDescription>請立即複製並安全保存。關閉此 dialog 後無法再次取得。</DialogDescription>
          </DialogHeader>
          <pre className="bg-muted p-3 rounded text-xs overflow-x-auto break-all">
            {tokenDialog}
          </pre>
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

function CreateAllocationDialog({
  open,
  onOpenChange,
  members,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  members: AdminMember[];
  onCreated: (token: string) => void;
}) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const form = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: { resource_model: "", is_service_allocation: false },
  });

  // Phase 5: pull catalog models from admin endpoint (unfiltered) so admin
  // sees every slug they can allocate, regardless of own tag membership.
  const catalogQuery = useQuery<Array<{ slug: string; display_name: string; provider: string }>, ApiError>({
    queryKey: ["admin", "catalog-models-admin"],
    queryFn: () =>
      api<Array<{ slug: string; display_name: string; provider: string }>>(
        "/admin/catalog/models",
      ),
    enabled: open,
  });

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      const created = await api<{ token: string; allocation: AdminAllocation }>(
        "/admin/allocations",
        {
          method: "POST",
          body: JSON.stringify({
            member_id: values.member_id,
            resource_model: values.resource_model,
            quota_tokens_per_month: values.quota_tokens_per_month,
            is_service_allocation: values.is_service_allocation,
            note: values.note,
          }),
        },
      );
      queryClient.invalidateQueries({ queryKey: ["admin", "allocations"] });
      onCreated((created as unknown as { token: string }).token);
      onOpenChange(false);
      form.reset();
    } catch (err) {
      const e = err as ApiError;
      toast({ title: "建立失敗", description: e.message, variant: "destructive" });
    }
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新增分配</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={onSubmit} className="space-y-4">
            <FormField
              control={form.control}
              name="member_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>成員</FormLabel>
                  <Select value={field.value ?? ""} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="選擇成員" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {members.map((m) => (
                        <SelectItem key={m.id} value={m.id}>
                          {m.email}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="resource_model"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>模型</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value || undefined}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder={
                          catalogQuery.isLoading
                            ? "載入 catalog…"
                            : (catalogQuery.data?.length ?? 0) === 0
                              ? "catalog 是空的；先去「Catalog 管理」加入"
                              : "選擇 model"
                        } />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {catalogQuery.data?.map((m) => (
                        <SelectItem key={m.slug} value={m.slug}>
                          {m.slug}
                          <span className="text-muted-foreground ml-1">
                            （{m.display_name}）
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="quota_tokens_per_month"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>月度配額 tokens（可選；空白=無限額）</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      value={field.value ?? ""}
                      onChange={(e) =>
                        field.onChange(e.target.value ? Number(e.target.value) : undefined)
                      }
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                建立
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
