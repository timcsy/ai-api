import * as React from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { MoreHorizontal } from "lucide-react";
import { z } from "zod";

import { Alert, AlertDescription } from "@/components/ui/alert";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
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
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import { useToast } from "@/components/ui/use-toast";
import { ApiError, api } from "@/lib/api-client";
import { statusLabel } from "@/lib/status-label";

interface AdminMember {
  id: string;
  email: string;
  provider: string;
  status: string;
  is_admin: boolean;
  created_at: string;
  has_password: boolean;
  tags: string[];
}

interface BulkOpResult {
  changed?: number;
  granted?: number;
  skipped?: number;
  failed: number;
  results: { member_id: string; status: string; reason: string | null }[];
}

const createSchema = z
  .object({
    // spec 055: 登入識別碼——帳號或 email 皆可，'@' 自由允許（不強制 email 格式）；
    // 僅結構限制：非空、不可含空白。
    email: z
      .string()
      .trim()
      .min(1, "必填")
      .refine((v) => !/\s/.test(v), "不可含空白"),
    provider: z.enum(["local_password", "external", "google_oidc"]),
    initial_password: z.string().min(12, "密碼至少 12 字元").optional().or(z.literal("")),
    send_invitation: z.boolean().default(false),
  })
  .refine(
    (data) => data.provider !== "local_password" || !!data.initial_password,
    { message: "local_password 需要初始密碼", path: ["initial_password"] },
  );

type CreateForm = z.infer<typeof createSchema>;

export function AdminMembersPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [createOpen, setCreateOpen] = React.useState(false);
  const [batchCreateOpen, setBatchCreateOpen] = React.useState(false);
  const [batchDeleteOpen, setBatchDeleteOpen] = React.useState(false);
  const [batchTagsOpen, setBatchTagsOpen] = React.useState(false);
  const [batchAllocateOpen, setBatchAllocateOpen] = React.useState(false);
  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  // Filters (client-side; member counts are small). search matches email/label.
  const [search, setSearch] = React.useState("");
  const [statusF, setStatusF] = React.useState("all");
  const [providerF, setProviderF] = React.useState("all");
  const [tagF, setTagF] = React.useState("all");
  const [adminOnly, setAdminOnly] = React.useState(false);
  const [confirm, setConfirm] = React.useState<
    | { kind: "demote"; member: AdminMember }
    | { kind: "promote"; member: AdminMember }
    | { kind: "disable"; member: AdminMember }
    | { kind: "enable"; member: AdminMember }
    | { kind: "delete"; member: AdminMember }
    | null
  >(null);

  const toggleOne = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const query = useQuery<AdminMember[], ApiError>({
    queryKey: ["admin", "members"],
    queryFn: () => api<AdminMember[]>("/admin/members"),
    staleTime: 30_000,
  });

  const patchMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api<AdminMember>(`/admin/members/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "members"] });
    },
    onError: (err: ApiError) => {
      const msg =
        err.code === "last_admin_cannot_demote"
          ? "至少需保留一個 admin"
          : err.message;
      toast({ title: "操作失敗", description: msg, variant: "destructive" });
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => api(`/admin/members/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "members"] });
      toast({ title: "成員已刪除" });
    },
    onError: (err: ApiError) => {
      toast({ title: "刪除失敗", description: err.message, variant: "destructive" });
    },
  });

  interface BulkDeleteResult {
    deleted: number;
    failed: number;
    results: { member_id: string; status: string; reason: string | null }[];
  }
  const bulkDeleteMut = useMutation<BulkDeleteResult, ApiError, string[]>({
    mutationFn: (ids) =>
      api<BulkDeleteResult>("/admin/members/bulk-delete", {
        method: "POST",
        body: JSON.stringify({ member_ids: ids }),
      }),
    onSuccess: (r) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "members"] });
      setSelected(new Set());
      setBatchDeleteOpen(false);
      const reasons = r.results
        .filter((x) => x.status === "failed")
        .map((x) => x.reason)
        .filter(Boolean);
      toast({
        title: `已刪除 ${r.deleted} 位${r.failed ? `，${r.failed} 位失敗` : ""}`,
        description: reasons.length ? `失敗原因：${reasons.join("、")}` : undefined,
        variant: r.failed ? "destructive" : "default",
      });
    },
    onError: (err) => {
      toast({ title: "批次刪除失敗", description: err.message, variant: "destructive" });
    },
  });

  const bulkToast = (verb: string, r: BulkOpResult) => {
    const ok = r.changed ?? r.granted ?? 0;
    const parts = [`${verb} ${ok} 位`];
    if (r.skipped) parts.push(`略過 ${r.skipped}`);
    if (r.failed) parts.push(`失敗 ${r.failed}`);
    const reasons = Array.from(
      new Set(r.results.filter((x) => x.status === "failed").map((x) => x.reason).filter(Boolean)),
    );
    toast({
      title: parts.join("、"),
      description: reasons.length ? `失敗原因：${reasons.join("、")}` : undefined,
      variant: r.failed ? "destructive" : "default",
    });
    void queryClient.invalidateQueries({ queryKey: ["admin", "members"] });
    void queryClient.invalidateQueries({ queryKey: ["admin", "tags"] });
    setSelected(new Set());
  };

  const bulkStatusMut = useMutation<BulkOpResult, ApiError, { ids: string[]; status: string }>({
    mutationFn: ({ ids, status }) =>
      api<BulkOpResult>("/admin/members/bulk-status", {
        method: "POST",
        body: JSON.stringify({ member_ids: ids, status }),
      }),
    onSuccess: (r, v) => bulkToast(v.status === "disabled" ? "已停用" : "已啟用", r),
    onError: (e) => toast({ title: "批次狀態變更失敗", description: e.message, variant: "destructive" }),
  });

  const bulkTagsMut = useMutation<BulkOpResult, ApiError, { ids: string[]; add: string[]; remove: string[] }>({
    mutationFn: ({ ids, add, remove }) =>
      api<BulkOpResult>("/admin/members/bulk-tags", {
        method: "POST",
        body: JSON.stringify({ member_ids: ids, add, remove }),
      }),
    onSuccess: (r) => {
      bulkToast("已更新標籤", r);
      setBatchTagsOpen(false);
    },
    onError: (e) => toast({ title: "批次標籤失敗", description: e.message, variant: "destructive" }),
  });

  const bulkAllocateMut = useMutation<
    BulkOpResult,
    ApiError,
    { ids: string[]; resource_model: string; quota_tokens_per_month?: number }
  >({
    mutationFn: ({ ids, resource_model, quota_tokens_per_month }) =>
      api<BulkOpResult>("/admin/members/bulk-allocate", {
        method: "POST",
        body: JSON.stringify({ member_ids: ids, resource_model, quota_tokens_per_month }),
      }),
    onSuccess: (r) => {
      bulkToast("已開通", r);
      setBatchAllocateOpen(false);
    },
    onError: (e) => toast({ title: "批次開通失敗", description: e.message, variant: "destructive" }),
  });

  const allTags = React.useMemo(() => {
    const s = new Set<string>();
    (query.data ?? []).forEach((m) => (m.tags ?? []).forEach((t) => s.add(t)));
    return Array.from(s).sort();
  }, [query.data]);

  const filtered = React.useMemo(() => {
    const term = search.trim().toLowerCase();
    return (query.data ?? []).filter((m) => {
      if (term && !m.email.toLowerCase().includes(term)) return false;
      if (statusF !== "all" && m.status !== statusF) return false;
      if (providerF !== "all" && m.provider !== providerF) return false;
      if (tagF !== "all" && !(m.tags ?? []).includes(tagF)) return false;
      if (adminOnly && !m.is_admin) return false;
      return true;
    });
  }, [query.data, search, statusF, providerF, tagF, adminOnly]);

  const filteredIds = filtered.map((m) => m.id);
  const allFilteredSelected = filtered.length > 0 && filteredIds.every((id) => selected.has(id));

  const performConfirmed = async () => {
    if (!confirm) return;
    const { kind, member } = confirm;
    setConfirm(null);
    if (kind === "promote") await patchMut.mutateAsync({ id: member.id, body: { is_admin: true } });
    if (kind === "demote") await patchMut.mutateAsync({ id: member.id, body: { is_admin: false } });
    if (kind === "disable") await patchMut.mutateAsync({ id: member.id, body: { status: "disabled" } });
    if (kind === "enable") await patchMut.mutateAsync({ id: member.id, body: { status: "active" } });
    if (kind === "delete") await deleteMut.mutateAsync(member.id);
  };

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">成員管理</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setBatchCreateOpen(true)}>批次新增</Button>
          <Button onClick={() => setCreateOpen(true)}>新增成員</Button>
        </div>
      </div>

      {/* Filter bar — narrow the list, then select-all + batch acts on the result */}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜尋帳號 / email"
          className="h-9 w-full sm:w-56"
        />
        <Select value={statusF} onValueChange={setStatusF}>
          <SelectTrigger className="h-9 w-[120px]"><SelectValue placeholder="狀態" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部狀態</SelectItem>
            <SelectItem value="active">啟用</SelectItem>
            <SelectItem value="disabled">停用</SelectItem>
          </SelectContent>
        </Select>
        <Select value={providerF} onValueChange={setProviderF}>
          <SelectTrigger className="h-9 w-[130px]"><SelectValue placeholder="登入方式" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部登入</SelectItem>
            <SelectItem value="google_oidc">google_oidc</SelectItem>
            <SelectItem value="local_password">local_password</SelectItem>
            <SelectItem value="external">external</SelectItem>
          </SelectContent>
        </Select>
        <Select value={tagF} onValueChange={setTagF}>
          <SelectTrigger className="h-9 w-[130px]"><SelectValue placeholder="標籤" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部標籤</SelectItem>
            {allTags.map((t) => (
              <SelectItem key={t} value={t}>{t}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant={adminOnly ? "default" : "outline"}
          size="sm"
          className="h-9"
          onClick={() => setAdminOnly((v) => !v)}
        >
          僅管理員
        </Button>
        {(search || statusF !== "all" || providerF !== "all" || tagF !== "all" || adminOnly) && (
          <Button
            variant="ghost"
            size="sm"
            className="h-9"
            onClick={() => {
              setSearch("");
              setStatusF("all");
              setProviderF("all");
              setTagF("all");
              setAdminOnly(false);
            }}
          >
            清除篩選
          </Button>
        )}
        <span className="text-sm text-muted-foreground ml-auto">
          {filtered.length}{query.data && filtered.length !== query.data.length ? ` / ${query.data.length}` : ""} 位
        </span>
      </div>

      {selected.size > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-muted/40 px-3 py-2">
          <span className="text-sm">已選 {selected.size} 位</span>
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>清除選取</Button>
            <Button variant="outline" size="sm" onClick={() => bulkStatusMut.mutate({ ids: Array.from(selected), status: "active" })}>批次啟用</Button>
            <Button variant="outline" size="sm" onClick={() => bulkStatusMut.mutate({ ids: Array.from(selected), status: "disabled" })}>批次停用</Button>
            <Button variant="outline" size="sm" onClick={() => setBatchTagsOpen(true)}>批次標籤</Button>
            <Button variant="outline" size="sm" onClick={() => setBatchAllocateOpen(true)}>批次開通模型</Button>
            <Button variant="destructive" size="sm" onClick={() => setBatchDeleteOpen(true)}>批次刪除</Button>
          </div>
        </div>
      )}

      {query.isLoading && <p className="text-muted-foreground">載入中…</p>}
      {query.error && (
        <Alert variant="destructive">
          <AlertDescription>無法載入：{query.error.message}</AlertDescription>
        </Alert>
      )}

      {query.data && (
        <Table className="responsive-table">
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <Checkbox
                  aria-label="全選"
                  checked={allFilteredSelected}
                  onCheckedChange={(c) =>
                    setSelected((prev) => {
                      const next = new Set(prev);
                      if (c) filteredIds.forEach((id) => next.add(id));
                      else filteredIds.forEach((id) => next.delete(id));
                      return next;
                    })
                  }
                />
              </TableHead>
              <TableHead>Email</TableHead>
              <TableHead>登入方式</TableHead>
              <TableHead>狀態</TableHead>
              <TableHead>管理員</TableHead>
              <TableHead>標籤</TableHead>
              <TableHead>建立時間</TableHead>
              <TableHead className="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((m) => (
              <TableRow key={m.id} data-state={selected.has(m.id) ? "selected" : undefined}>
                <TableCell data-label="選取">
                  <Checkbox
                    aria-label={`選取 ${m.email}`}
                    checked={selected.has(m.id)}
                    onCheckedChange={() => toggleOne(m.id)}
                  />
                </TableCell>
                <TableCell className="font-medium" data-label="Email">
                  <Link to={`/admin/member/${m.id}`} className="block max-w-[180px] truncate text-primary hover:underline">
                    {m.email}
                  </Link>
                </TableCell>
                <TableCell data-label="登入方式">{m.provider}</TableCell>
                <TableCell data-label="狀態">
                  <Badge variant={m.status === "active" ? "default" : "secondary"}>{statusLabel(m.status)}</Badge>
                </TableCell>
                <TableCell data-label="管理員">
                  {m.is_admin && <Badge>admin</Badge>}
                </TableCell>
                <TableCell data-label="標籤">
                  <MemberTagsCell memberId={m.id} tags={m.tags ?? []} />
                </TableCell>
                <TableCell className="text-xs text-muted-foreground" data-label="建立時間">
                  {new Date(m.created_at).toLocaleDateString("zh-TW")}
                </TableCell>
                <TableCell className="text-right" data-label="操作">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      {m.is_admin ? (
                        <DropdownMenuItem
                          onClick={() => setConfirm({ kind: "demote", member: m })}
                        >
                          降為一般成員
                        </DropdownMenuItem>
                      ) : (
                        <DropdownMenuItem
                          onClick={() => setConfirm({ kind: "promote", member: m })}
                        >
                          升為管理員
                        </DropdownMenuItem>
                      )}
                      {m.status === "active" ? (
                        <DropdownMenuItem
                          onClick={() => setConfirm({ kind: "disable", member: m })}
                        >
                          停用
                        </DropdownMenuItem>
                      ) : (
                        <DropdownMenuItem
                          onClick={() => setConfirm({ kind: "enable", member: m })}
                        >
                          啟用
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => setConfirm({ kind: "delete", member: m })}
                      >
                        刪除
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                  {query.data.length === 0 ? "尚無成員" : "無符合條件的成員"}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}

      <CreateMemberDialog open={createOpen} onOpenChange={setCreateOpen} />

      <AlertDialog open={!!confirm} onOpenChange={(open) => !open && setConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirm?.kind === "delete" ? "確認刪除成員" : "確認操作"}
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              {confirm?.kind === "delete" ? (
                <div className="space-y-2">
                  <p>
                    將刪除成員 <strong>{confirm.member.email}</strong>，並一併撤回並移除其
                    <strong>所有分配與應用金鑰</strong>。
                  </p>
                  <p>該成員正在使用的金鑰會<strong>立即失效</strong>；過往<strong>用量紀錄會保留</strong>供稽核。此操作無法復原。</p>
                </div>
              ) : (
                <span>{confirm && `對 ${confirm.member.email} 執行：${confirm.kind}`}</span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={() => void performConfirmed()}>確認</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={batchDeleteOpen} onOpenChange={setBatchDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>批次刪除 {selected.size} 位成員</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2">
                <p>將對選取的 <strong>{selected.size}</strong> 位成員執行安全刪除，一併移除各自的分配與應用金鑰。</p>
                <p>正在使用的金鑰會<strong>立即失效</strong>；過往<strong>用量紀錄會保留</strong>。刪不掉的（如自己 / 最後一位管理員）會略過並回報。此操作無法復原。</p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => void bulkDeleteMut.mutateAsync(Array.from(selected))}
            >
              確認刪除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <BatchCreateMembersDialog open={batchCreateOpen} onOpenChange={setBatchCreateOpen} />

      <BatchTagsDialog
        open={batchTagsOpen}
        onOpenChange={setBatchTagsOpen}
        count={selected.size}
        allTags={allTags}
        pending={bulkTagsMut.isPending}
        onSubmit={(add, remove) => bulkTagsMut.mutate({ ids: Array.from(selected), add, remove })}
      />

      <BatchAllocateDialog
        open={batchAllocateOpen}
        onOpenChange={setBatchAllocateOpen}
        count={selected.size}
        pending={bulkAllocateMut.isPending}
        onSubmit={(model, quota) =>
          bulkAllocateMut.mutate({
            ids: Array.from(selected),
            resource_model: model,
            quota_tokens_per_month: quota,
          })
        }
      />
    </div>
  );
}

function BatchTagsDialog({
  open,
  onOpenChange,
  count,
  allTags,
  pending,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  count: number;
  allTags: string[];
  pending: boolean;
  onSubmit: (add: string[], remove: string[]) => void;
}) {
  const [addText, setAddText] = React.useState("");
  const [remove, setRemove] = React.useState<Set<string>>(new Set());
  const add = addText
    .split(/[\s,，、]+/)
    .map((t) => t.trim().toLowerCase())
    .filter(Boolean);

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) {
          setAddText("");
          setRemove(new Set());
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>批次標籤 · {count} 位</DialogTitle>
          <DialogDescription>對選取的成員加上或移除標籤。</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1">
            <label className="text-sm font-medium">加標籤</label>
            <Input
              value={addText}
              onChange={(e) => setAddText(e.target.value)}
              placeholder="以空白或逗號分隔，例如 class-a 三年級"
            />
          </div>
          {allTags.length > 0 && (
            <div className="space-y-1">
              <label className="text-sm font-medium">移除標籤（點選）</label>
              <div className="flex flex-wrap gap-1">
                {allTags.map((t) => {
                  const on = remove.has(t);
                  return (
                    <Badge
                      key={t}
                      variant={on ? "destructive" : "secondary"}
                      className="cursor-pointer"
                      onClick={() =>
                        setRemove((prev) => {
                          const next = new Set(prev);
                          if (next.has(t)) next.delete(t);
                          else next.add(t);
                          return next;
                        })
                      }
                    >
                      {t}
                      {on ? " ✕" : ""}
                    </Badge>
                  );
                })}
              </div>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button
            disabled={pending || (add.length === 0 && remove.size === 0)}
            onClick={() => onSubmit(add, Array.from(remove))}
          >
            套用
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function BatchAllocateDialog({
  open,
  onOpenChange,
  count,
  pending,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  count: number;
  pending: boolean;
  onSubmit: (resourceModel: string, quota: number | undefined) => void;
}) {
  const [model, setModel] = React.useState("");
  const [quota, setQuota] = React.useState("");
  const models = useQuery<Array<{ slug: string }>, ApiError>({
    queryKey: ["admin", "catalog-models-admin"],
    queryFn: () => api<Array<{ slug: string }>>("/admin/catalog/models"),
    enabled: open,
    staleTime: 60_000,
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) {
          setModel("");
          setQuota("");
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>批次開通模型 · {count} 位</DialogTitle>
          <DialogDescription>
            為選取的成員各建立一筆分配（含預設金鑰）。已有該模型有效分配者自動略過。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1">
            <label className="text-sm font-medium">模型</label>
            <Select value={model} onValueChange={setModel}>
              <SelectTrigger><SelectValue placeholder="選擇模型" /></SelectTrigger>
              <SelectContent>
                {(models.data ?? []).map((m) => (
                  <SelectItem key={m.slug} value={m.slug}>{m.slug}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">每月 token 額度（選填，留空為無上限）</label>
            <Input
              type="number"
              min={0}
              value={quota}
              onChange={(e) => setQuota(e.target.value)}
              placeholder="例如 1000000"
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            disabled={pending || !model}
            onClick={() => onSubmit(model, quota.trim() ? Number(quota) : undefined)}
          >
            開通
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function MemberTagsCell({ memberId, tags }: { memberId: string; tags: string[] }) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [open, setOpen] = React.useState(false);
  const [newTag, setNewTag] = React.useState("");

  // Tags come from the member list row (no per-member N+1); mutations invalidate
  // the list so the row (and the tag filter) refresh.
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin", "members"] });
    void queryClient.invalidateQueries({ queryKey: ["admin", "tags"] });
  };

  const addMut = useMutation<string[], ApiError, string>({
    mutationFn: (tag) =>
      api<string[]>(`/admin/members/${memberId}/tags`, {
        method: "POST",
        body: JSON.stringify({ tags: [tag] }),
      }),
    onSuccess: () => {
      setNewTag("");
      invalidate();
    },
    onError: (e) => toast({ title: "加標籤失敗", description: e.message, variant: "destructive" }),
  });

  const removeMut = useMutation<void, ApiError, string>({
    mutationFn: (tag) =>
      api<void>(`/admin/members/${memberId}/tags?tag=${encodeURIComponent(tag)}`, {
        method: "DELETE",
      }),
    onSuccess: invalidate,
    onError: (e) => toast({ title: "移除標籤失敗", description: e.message, variant: "destructive" }),
  });

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {tags.map((tag) => (
        <Badge
          key={tag}
          variant="secondary"
          className="cursor-pointer text-xs"
          title="點擊移除"
          onClick={() => removeMut.mutate(tag)}
        >
          {tag} <span className="ml-1 text-muted-foreground">×</span>
        </Badge>
      ))}
      {!open ? (
        <Button
          size="icon"
          variant="ghost"
          className="h-6 w-6 text-muted-foreground"
          title="加標籤"
          onClick={() => setOpen(true)}
        >
          +
        </Button>
      ) : (
        <div className="flex items-center gap-1">
          <Input
            value={newTag}
            onChange={(e) => setNewTag(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                const t = newTag.trim().toLowerCase();
                if (t) addMut.mutate(t);
              }
              if (e.key === "Escape") {
                setOpen(false);
                setNewTag("");
              }
            }}
            onBlur={() => {
              const t = newTag.trim().toLowerCase();
              if (t) {
                addMut.mutate(t);
              } else {
                setOpen(false);
              }
            }}
            autoFocus
            className="h-7 w-24 text-xs"
            placeholder="標籤"
          />
        </div>
      )}
    </div>
  );
}

interface BulkCreateResult {
  created: number;
  exists: number;
  invalid: number;
  duplicate: number;
  results: { email: string; status: string; invitation_url: string | null }[];
}

const BULK_STATUS_LABEL: Record<string, string> = {
  created: "已建立",
  exists: "已存在",
  invalid: "格式錯",
  duplicate: "重複",
};

function BatchCreateMembersDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [emails, setEmails] = React.useState("");
  const [result, setResult] = React.useState<BulkCreateResult | null>(null);

  const mut = useMutation<BulkCreateResult, ApiError, string>({
    mutationFn: (text) =>
      api<BulkCreateResult>("/admin/members/bulk-create", {
        method: "POST",
        body: JSON.stringify({ emails: text }),
      }),
    onSuccess: (r) => {
      setResult(r);
      queryClient.invalidateQueries({ queryKey: ["admin", "members"] });
    },
    onError: (e) => toast({ title: "批次建立失敗", description: e.message, variant: "destructive" }),
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) {
          setEmails("");
          setResult(null);
        }
      }}
    >
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>批次新增成員（本地帳號）</DialogTitle>
          <DialogDescription>
            每行一個 email，逐筆建立 local_password 成員並各自產生邀請連結。
          </DialogDescription>
        </DialogHeader>
        <Textarea
          value={emails}
          onChange={(e) => setEmails(e.target.value)}
          rows={6}
          placeholder={"每行一個 email\nalice@example.com\nbob@example.com"}
        />
        <DialogFooter>
          <Button
            disabled={!emails.trim() || mut.isPending}
            onClick={() => mut.mutate(emails)}
          >
            批次建立
          </Button>
        </DialogFooter>

        {result && (
          <div className="space-y-2 border-t pt-3">
            <p className="text-sm text-muted-foreground">
              已建立 {result.created}・已存在 {result.exists}・格式錯 {result.invalid}・重複 {result.duplicate}
            </p>
            <ul className="space-y-1 text-sm">
              {result.results.map((r, i) => (
                <li key={`${r.email}-${i}`} className="flex items-center justify-between gap-2">
                  <span className="font-mono break-all">{r.email}</span>
                  <span className="flex items-center gap-2 shrink-0">
                    <Badge variant={r.status === "created" ? "default" : "secondary"}>
                      {BULK_STATUS_LABEL[r.status] ?? r.status}
                    </Badge>
                    {r.invitation_url && (
                      <a
                        href={r.invitation_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary underline text-xs"
                      >
                        邀請連結
                      </a>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function CreateMemberDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const form = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      email: "",
      provider: "local_password",
      initial_password: "",
      send_invitation: false,
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await api("/admin/members", {
        method: "POST",
        body: JSON.stringify({
          email: values.email,
          provider: values.provider,
          initial_password: values.initial_password || undefined,
          send_invitation: values.send_invitation,
        }),
      });
      queryClient.invalidateQueries({ queryKey: ["admin", "members"] });
      toast({ title: "成員已建立" });
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
          <DialogTitle>新增成員</DialogTitle>
          <DialogDescription>建立後可在列表升管理員 / 停用</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={onSubmit} className="space-y-4">
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>帳號 / Email</FormLabel>
                  <FormControl>
                    <Input type="text" placeholder="帳號或 email" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="provider"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>登入方式</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="local_password">local_password</SelectItem>
                      <SelectItem value="external">external</SelectItem>
                      <SelectItem value="google_oidc">google_oidc</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            {form.watch("provider") === "local_password" && (
              <FormField
                control={form.control}
                name="initial_password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>初始密碼</FormLabel>
                    <FormControl>
                      <Input type="password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}
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
