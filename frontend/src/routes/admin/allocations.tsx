import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { MoreHorizontal } from "lucide-react";
import { z } from "zod";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { QuarantineReasonBadge } from "@/components/quarantine-reason-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { statusLabel } from "@/lib/status-label";

interface AdminAllocation {
  id: string;
  member_id: string;
  subject_snapshot: string;
  resource_model: string;
  display_name?: string | null;
  status: string;
  quota_tokens_per_month: number | null;
  quota_cost_usd_per_month: string | null;
  is_service_allocation: boolean;
  quota_locked: boolean;
  token_prefix: string;
  created_at: string;
}

interface AdminMember {
  id: string;
  email: string;
}

interface ReclaimLock {
  member_id: string;
  member_email: string | null;
  model_slug: string;
  locked_at: string;
  locked_by: string;
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
  const [quotaTarget, setQuotaTarget] = React.useState<AdminAllocation | null>(null);
  const [quotaValue, setQuotaValue] = React.useState("");
  const [costValue, setCostValue] = React.useState("");
  // Filters (client-side) + batch selection.
  const [search, setSearch] = React.useState("");
  const [statusF, setStatusF] = React.useState("all"); // all=進行中(不含撤回); or a specific status incl. revoked
  const [modelF, setModelF] = React.useState("all");
  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  const [batchQuotaOpen, setBatchQuotaOpen] = React.useState(false);

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
      queryClient.invalidateQueries({ queryKey: ["admin", "self-service-locks"] });
      toast({ title: "已撤回" });
    },
  });
  const pauseResumeMut = useMutation<unknown, ApiError, { id: string; action: "pause" | "resume" }>({
    mutationFn: ({ id, action }) => api(`/admin/allocations/${id}/${action}`, { method: "POST" }),
    onSuccess: (_d, { action }) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "allocations"] });
      toast({ title: action === "pause" ? "已暫停" : "已恢復" });
    },
    onError: (e) => toast({ title: "操作失敗", description: e.message, variant: "destructive" }),
  });
  const unquarantineMut = useMutation<unknown, ApiError, string>({
    mutationFn: (id) => api(`/admin/allocations/${id}/unquarantine`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "allocations"] });
      toast({ title: "已解除隔離" });
    },
    onError: (e) => toast({ title: "解除失敗", description: e.message, variant: "destructive" }),
  });

  const locksQuery = useQuery<ReclaimLock[], ApiError>({
    queryKey: ["admin", "self-service-locks"],
    queryFn: () => api<ReclaimLock[]>("/admin/self-service-locks"),
  });
  const unlockMut = useMutation<void, ApiError, { member_id: string; model_slug: string }>({
    mutationFn: (body) =>
      api("/admin/self-service-locks/unlock", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "self-service-locks"] });
      toast({ title: "已解鎖，成員可重新自助領取" });
    },
    onError: (e) => toast({ title: "解鎖失敗", description: e.message, variant: "destructive" }),
  });

  interface BulkResult {
    changed: number;
    failed: number;
    results: { allocation_id: string; status: string; reason: string | null }[];
  }
  const bulkToast = (verb: string, r: BulkResult) => {
    const reasons = Array.from(
      new Set(r.results.filter((x) => x.status === "failed").map((x) => x.reason).filter(Boolean)),
    );
    toast({
      title: `${verb} ${r.changed} 筆${r.failed ? `，失敗 ${r.failed}` : ""}`,
      description: reasons.length ? `失敗原因：${reasons.join("、")}` : undefined,
      variant: r.failed ? "destructive" : "default",
    });
    void queryClient.invalidateQueries({ queryKey: ["admin", "allocations"] });
    void queryClient.invalidateQueries({ queryKey: ["admin", "self-service-locks"] });
    setSelected(new Set());
  };
  const bulkActionMut = useMutation<BulkResult, ApiError, { ids: string[]; action: string; verb: string }>({
    mutationFn: ({ ids, action }) =>
      api<BulkResult>("/admin/allocations/bulk-action", {
        method: "POST",
        body: JSON.stringify({ allocation_ids: ids, action }),
      }),
    onSuccess: (r, v) => bulkToast(v.verb, r),
    onError: (e) => toast({ title: "批次操作失敗", description: e.message, variant: "destructive" }),
  });
  const bulkQuotaMut = useMutation<
    BulkResult,
    ApiError,
    { ids: string[]; quota_tokens_per_month?: number | null; quota_cost_usd_per_month?: number | null }
  >({
    mutationFn: ({ ids, quota_tokens_per_month, quota_cost_usd_per_month }) => {
      const body: Record<string, unknown> = { allocation_ids: ids };
      if (quota_tokens_per_month !== undefined) body.quota_tokens_per_month = quota_tokens_per_month;
      if (quota_cost_usd_per_month !== undefined) body.quota_cost_usd_per_month = quota_cost_usd_per_month;
      return api<BulkResult>("/admin/allocations/bulk-quota", {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    onSuccess: (r) => {
      bulkToast("已調整配額", r);
      setBatchQuotaOpen(false);
    },
    onError: (e) => toast({ title: "批次配額失敗", description: e.message, variant: "destructive" }),
  });

  const memberEmail = (a: AdminAllocation) =>
    memberById.get(a.member_id)?.email ?? a.subject_snapshot;

  const allModels = React.useMemo(() => {
    const s = new Set<string>();
    (allocsQuery.data ?? []).forEach((a) => s.add(a.resource_model));
    return Array.from(s).sort();
  }, [allocsQuery.data]);

  const filtered = React.useMemo(() => {
    const term = search.trim().toLowerCase();
    return (allocsQuery.data ?? []).filter((a) => {
      if (serviceOnly && !a.is_service_allocation) return false;
      // status: "all" = everything except revoked; a specific value matches exactly.
      if (statusF === "all" ? a.status === "revoked" : a.status !== statusF) return false;
      if (modelF !== "all" && a.resource_model !== modelF) return false;
      if (term) {
        const hay = `${memberEmail(a)} ${a.resource_model} ${a.display_name ?? ""}`.toLowerCase();
        if (!hay.includes(term)) return false;
      }
      return true;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allocsQuery.data, search, statusF, modelF, serviceOnly, memberById]);

  const filteredIds = filtered.map((a) => a.id);
  const allFilteredSelected = filtered.length > 0 && filteredIds.every((id) => selected.has(id));
  const revokedCount = (allocsQuery.data ?? []).filter((a) => a.status === "revoked").length;
  const toggleOne = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-3xl font-bold">分配管理</h1>
        <Button onClick={() => setCreateOpen(true)}>新增分配</Button>
      </div>

      {/* Filter bar — narrow, then select-all + batch acts on the result */}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜尋成員 / 模型"
          className="h-9 w-full sm:w-56"
        />
        <Select value={statusF} onValueChange={setStatusF}>
          <SelectTrigger className="h-9 w-[150px]"><SelectValue placeholder="狀態" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">進行中（不含撤回）</SelectItem>
            <SelectItem value="active">啟用</SelectItem>
            <SelectItem value="paused">暫停</SelectItem>
            <SelectItem value="quarantined">隔離</SelectItem>
            <SelectItem value="revoked">已撤回{revokedCount > 0 ? `（${revokedCount}）` : ""}</SelectItem>
          </SelectContent>
        </Select>
        <Select value={modelF} onValueChange={setModelF}>
          <SelectTrigger className="h-9 w-[160px]"><SelectValue placeholder="模型" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部模型</SelectItem>
            {allModels.map((m) => (
              <SelectItem key={m} value={m}>{m}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex items-center gap-2">
          <Switch id="service-only" checked={serviceOnly} onCheckedChange={setServiceOnly} />
          <Label htmlFor="service-only" className="text-sm">只看服務型</Label>
        </div>
        {(search || statusF !== "all" || modelF !== "all" || serviceOnly) && (
          <Button
            variant="ghost"
            size="sm"
            className="h-9"
            onClick={() => {
              setSearch("");
              setStatusF("all");
              setModelF("all");
              setServiceOnly(false);
            }}
          >
            清除篩選
          </Button>
        )}
        <span className="text-sm text-muted-foreground ml-auto">{filtered.length} 筆</span>
      </div>

      {selected.size > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-muted/40 px-3 py-2">
          <span className="text-sm">已選 {selected.size} 筆</span>
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>清除選取</Button>
            <Button variant="outline" size="sm" onClick={() => bulkActionMut.mutate({ ids: Array.from(selected), action: "pause", verb: "已暫停" })}>批次暫停</Button>
            <Button variant="outline" size="sm" onClick={() => bulkActionMut.mutate({ ids: Array.from(selected), action: "resume", verb: "已恢復" })}>批次恢復</Button>
            <Button variant="outline" size="sm" onClick={() => bulkActionMut.mutate({ ids: Array.from(selected), action: "unquarantine", verb: "已解除隔離" })}>批次解除隔離</Button>
            <Button variant="outline" size="sm" onClick={() => setBatchQuotaOpen(true)}>批次調配額</Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => {
                if (confirm(`批次撤回 ${selected.size} 筆分配？此為終局，token 將立即失效、無法復原。`))
                  bulkActionMut.mutate({ ids: Array.from(selected), action: "revoke", verb: "已撤回" });
              }}
            >
              批次撤回
            </Button>
          </div>
        </div>
      )}

      {allocsQuery.isLoading && <p className="text-muted-foreground">載入中…</p>}
      {allocsQuery.error && (
        <Alert variant="destructive">
          <AlertDescription>無法載入：{allocsQuery.error.message}</AlertDescription>
        </Alert>
      )}

      {allocsQuery.data && (
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
              <TableRow key={a.id} data-state={selected.has(a.id) ? "selected" : undefined}>
                <TableCell data-label="選取">
                  <Checkbox
                    aria-label={`選取 ${memberEmail(a)} 的 ${a.resource_model}`}
                    checked={selected.has(a.id)}
                    onCheckedChange={() => toggleOne(a.id)}
                  />
                </TableCell>
                <TableCell className="font-medium" data-label="成員">
                  <span className="block max-w-[180px] truncate">
                    {memberById.get(a.member_id)?.email ?? a.subject_snapshot}
                  </span>
                </TableCell>
                <TableCell data-label="模型">
                  <div className="min-w-0">
                    {a.display_name && <div className="text-xs font-medium">{a.display_name}</div>}
                    <span className="font-mono text-xs text-muted-foreground break-all">{a.resource_model}</span>
                    {catalogSlugs.data && !knownSlugs.has(a.resource_model) && (
                      <Badge variant="outline" className="ml-2 shrink-0 whitespace-nowrap text-amber-700 border-amber-500">
                        ⚠ 已不在目錄
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell data-label="狀態">
                  {a.status === "quarantined" ? (
                    <QuarantineReasonBadge allocationId={a.id} status="quarantined" />
                  ) : a.status === "paused" ? (
                    <QuarantineReasonBadge allocationId={a.id} status="paused" />
                  ) : (
                    <Badge variant={a.status === "active" ? "default" : "secondary"}>
                      {statusLabel(a.status)}
                    </Badge>
                  )}
                </TableCell>
                <TableCell data-label="配額">{a.quota_tokens_per_month ?? "無限額"}</TableCell>
                <TableCell className="space-x-1" data-label="標籤">
                  {a.is_service_allocation && <Badge variant="outline">服務型</Badge>}
                  {a.quota_locked && <Badge variant="outline">已鎖定</Badge>}
                </TableCell>
                <TableCell className="font-mono text-xs" data-label="Token 前綴">{a.token_prefix}…</TableCell>
                <TableCell className="text-right" data-label="操作">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" aria-label="操作">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() => {
                          setQuotaTarget(a);
                          setQuotaValue(a.quota_tokens_per_month != null ? String(a.quota_tokens_per_month) : "");
                          setCostValue(a.quota_cost_usd_per_month != null ? String(Number(a.quota_cost_usd_per_month)) : "");
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
                      {a.status === "active" && (
                        <DropdownMenuItem
                          onClick={() => pauseResumeMut.mutate({ id: a.id, action: "pause" })}
                        >
                          暫停（可恢復、保留 token）
                        </DropdownMenuItem>
                      )}
                      {a.status === "paused" && (
                        <DropdownMenuItem
                          onClick={() => pauseResumeMut.mutate({ id: a.id, action: "resume" })}
                        >
                          恢復
                        </DropdownMenuItem>
                      )}
                      {a.status === "quarantined" && (
                        <DropdownMenuItem
                          onClick={() => unquarantineMut.mutate(a.id)}
                        >
                          解除隔離（恢復為可用）
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => {
                          if (confirm(`撤回 ${a.token_prefix}… ？此為終局，token 將失效。`)) revokeMut.mutate(a.id);
                        }}
                      >
                        撤回（終局）
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                  {statusF === "all" && revokedCount > 0
                    ? `無進行中的分配（另有 ${revokedCount} 筆已撤回，狀態選「已撤回」可查看）`
                    : (allocsQuery.data?.length ?? 0) === 0
                      ? "尚無分配"
                      : "無符合條件的分配"}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}

      {(locksQuery.data?.length ?? 0) > 0 && (
        <div className="space-y-2">
          <h2 className="text-lg font-semibold">自助領取鎖定</h2>
          <p className="text-sm text-muted-foreground">
            這些（成員, 模型）的自助憑證被撤回後鎖定，解鎖後成員才能再次自助領取。
          </p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>成員</TableHead>
                <TableHead>模型</TableHead>
                <TableHead>鎖定時間</TableHead>
                <TableHead className="text-right">動作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {locksQuery.data?.map((lk) => (
                <TableRow key={`${lk.member_id}:${lk.model_slug}`}>
                  <TableCell className="font-medium">{lk.member_email ?? lk.member_id}</TableCell>
                  <TableCell className="font-mono text-xs">{lk.model_slug}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(lk.locked_at).toLocaleString("zh-TW")}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={unlockMut.isPending}
                      onClick={() =>
                        unlockMut.mutate({ member_id: lk.member_id, model_slug: lk.model_slug })
                      }
                    >
                      解鎖
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <CreateAllocationDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        members={membersQuery.data ?? []}
        onCreated={(token) => setTokenDialog(token)}
      />

      <BatchQuotaDialog
        open={batchQuotaOpen}
        onOpenChange={setBatchQuotaOpen}
        count={selected.size}
        pending={bulkQuotaMut.isPending}
        onSubmit={(tokens, cost) =>
          bulkQuotaMut.mutate({
            ids: Array.from(selected),
            ...(tokens !== undefined ? { quota_tokens_per_month: tokens } : {}),
            ...(cost !== undefined ? { quota_cost_usd_per_month: cost } : {}),
          })
        }
      />


      <Dialog open={!!tokenDialog} onOpenChange={(open) => !open && setTokenDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>分配已建立 — 此 token 只顯示一次</DialogTitle>
            <DialogDescription>請立即複製並安全保存。關閉此對話框後無法再次取得。</DialogDescription>
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

      <Dialog open={!!quotaTarget} onOpenChange={(open) => !open && setQuotaTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>調整月度配額</DialogTitle>
            <DialogDescription>兩種上限可同時設、任一達到即擋；留空＝該項無上限。</DialogDescription>
          </DialogHeader>
          <label className="text-sm font-medium">每月 token 上限</label>
          <Input
            type="number"
            min={0}
            value={quotaValue}
            placeholder="無限額"
            aria-label="月度配額"
            onChange={(e) => setQuotaValue(e.target.value)}
          />
          {quotaValue.trim() !== "" && !/^\d+$/.test(quotaValue.trim()) && (
            <p className="text-xs text-destructive">請填非負整數，或留空表示無限額。</p>
          )}
          <label className="text-sm font-medium mt-2">每月花費上限（USD）</label>
          <Input
            type="number"
            min={0}
            step="0.01"
            value={costValue}
            placeholder="無上限"
            aria-label="每月花費上限"
            onChange={(e) => setCostValue(e.target.value)}
          />
          {costValue.trim() !== "" && !(Number(costValue) >= 0) && (
            <p className="text-xs text-destructive">請填非負金額，或留空表示無上限。</p>
          )}
          <p className="text-xs text-muted-foreground">
            花費上限以 USD 統一治理所有端點（token / 頁 / 張 / 秒 / 分…）；只治理「已定價」的用量。
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setQuotaTarget(null)}>取消</Button>
            <Button
              disabled={
                (quotaValue.trim() !== "" && !/^\d+$/.test(quotaValue.trim())) ||
                (costValue.trim() !== "" && !(Number(costValue) >= 0))
              }
              onClick={() => {
                if (!quotaTarget) return;
                const v = quotaValue.trim();
                const c = costValue.trim();
                if (v !== "" && !/^\d+$/.test(v)) return;
                if (c !== "" && !(Number(c) >= 0)) return;
                patchMut.mutate({
                  id: quotaTarget.id,
                  body: {
                    quota_tokens_per_month: v === "" ? null : Number(v),
                    quota_cost_usd_per_month: c === "" ? null : Number(c),
                  },
                });
                setQuotaTarget(null);
              }}
            >
              套用
            </Button>
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
                            ? "載入目錄…"
                            : (catalogQuery.data?.length ?? 0) === 0
                              ? "目錄是空的；先去「模型目錄」加入"
                              : "選擇模型"
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

function BatchQuotaDialog({
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
  onSubmit: (tokens: number | null | undefined, cost: number | null | undefined) => void;
}) {
  const [setTokens, setSetTokens] = React.useState(true);
  const [tokenVal, setTokenVal] = React.useState("");
  const [setCost, setSetCost] = React.useState(false);
  const [costVal, setCostVal] = React.useState("");

  const reset = () => {
    setSetTokens(true);
    setTokenVal("");
    setSetCost(false);
    setCostVal("");
  };
  const tokenBad = setTokens && tokenVal.trim() !== "" && !/^\d+$/.test(tokenVal.trim());
  const costBad = setCost && costVal.trim() !== "" && !(Number(costVal) >= 0);

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) reset();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>批次調整配額 · {count} 筆</DialogTitle>
          <DialogDescription>
            勾選才變更該項；值留空＝該項設為無上限；不勾＝維持原值不動。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1">
            <label className="flex items-center gap-2 text-sm font-medium">
              <Checkbox checked={setTokens} onCheckedChange={(c) => setSetTokens(!!c)} />
              設定每月 token 上限
            </label>
            <Input
              type="number"
              min={0}
              disabled={!setTokens}
              value={tokenVal}
              placeholder="無上限"
              onChange={(e) => setTokenVal(e.target.value)}
            />
            {tokenBad && <p className="text-xs text-destructive">請填非負整數，或留空表示無上限。</p>}
          </div>
          <div className="space-y-1">
            <label className="flex items-center gap-2 text-sm font-medium">
              <Checkbox checked={setCost} onCheckedChange={(c) => setSetCost(!!c)} />
              設定每月花費上限（USD）
            </label>
            <Input
              type="number"
              min={0}
              step="0.01"
              disabled={!setCost}
              value={costVal}
              placeholder="無上限"
              onChange={(e) => setCostVal(e.target.value)}
            />
            {costBad && <p className="text-xs text-destructive">請填非負金額，或留空表示無上限。</p>}
          </div>
        </div>
        <DialogFooter>
          <Button
            disabled={pending || (!setTokens && !setCost) || tokenBad || costBad}
            onClick={() =>
              onSubmit(
                setTokens ? (tokenVal.trim() === "" ? null : Number(tokenVal)) : undefined,
                setCost ? (costVal.trim() === "" ? null : Number(costVal)) : undefined,
              )
            }
          >
            套用
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
