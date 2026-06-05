import * as React from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/use-toast";
import { AdminMemberCredentials } from "@/components/admin-member-credentials";
import { VisibilityDiagnose } from "@/components/visibility-diagnose";
import { ApiError, api } from "@/lib/api-client";
import { copyToClipboard } from "@/lib/clipboard";

interface AdminMember {
  id: string;
  email: string;
  provider: string;
  status: string;
  is_admin: boolean;
  created_at: string;
}

interface AdminAllocation {
  id: string;
  member_id: string;
  resource_model: string;
  display_name?: string | null;
  status: string;
  quota_tokens_per_month: number | null;
  token_prefix: string;
  created_at: string;
}

interface VisibleModel {
  slug: string;
  display_name: string;
  provider: string;
}

interface MemberTagDetail {
  tag: string;
  source: "manual" | "auto";
  rule_id: string | null;
}

export function AdminMemberDetailPage() {
  const { id } = useParams<{ id: string }>();
  const memberId = id ?? "";

  const membersQuery = useQuery<AdminMember[], ApiError>({
    queryKey: ["admin", "members"],
    queryFn: () => api<AdminMember[]>("/admin/members"),
  });
  const member = membersQuery.data?.find((m) => m.id === memberId);

  const tagsQuery = useQuery<MemberTagDetail[], ApiError>({
    queryKey: ["admin", "members", memberId, "tags", "detail"],
    queryFn: () => api<MemberTagDetail[]>(`/admin/members/${memberId}/tags/detail`),
    enabled: !!memberId,
  });

  const visibleQuery = useQuery<VisibleModel[], ApiError>({
    queryKey: ["admin", "members", memberId, "visible-models"],
    queryFn: () => api<VisibleModel[]>(`/admin/members/${memberId}/visible-models`),
    enabled: !!memberId && member?.status === "active",
  });

  const allocsQuery = useQuery<AdminAllocation[], ApiError>({
    queryKey: ["admin", "allocations"],
    queryFn: () => api<AdminAllocation[]>("/admin/allocations"),
  });
  const [showRevoked, setShowRevoked] = React.useState(false);
  const allMemberAllocs = (allocsQuery.data ?? []).filter((a) => a.member_id === memberId);
  const memberAllocs = allMemberAllocs.filter((a) => showRevoked || a.status !== "revoked");
  const revokedCount = allMemberAllocs.filter((a) => a.status === "revoked").length;

  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [createOpen, setCreateOpen] = React.useState(false);
  const [tokenDialog, setTokenDialog] = React.useState<string | null>(null);
  const [revokeTarget, setRevokeTarget] = React.useState<AdminAllocation | null>(null);

  const revokeMut = useMutation<void, ApiError, string>({
    mutationFn: (allocId) => api(`/admin/allocations/${allocId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "allocations"] });
      setRevokeTarget(null);
      toast({ title: "已撤回" });
    },
    onError: (e) => toast({ title: "撤回失敗", description: e.message, variant: "destructive" }),
  });
  const pauseResumeMut = useMutation<unknown, ApiError, { id: string; action: "pause" | "resume" }>({
    mutationFn: ({ id, action }) => api(`/admin/allocations/${id}/${action}`, { method: "POST" }),
    onSuccess: (_d, { action }) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "allocations"] });
      toast({ title: action === "pause" ? "已暫停" : "已恢復" });
    },
    onError: (e) => toast({ title: "操作失敗", description: e.message, variant: "destructive" }),
  });

  if (membersQuery.isLoading) return <div className="container mx-auto py-8">載入中…</div>;
  if (!member) {
    return (
      <div className="container mx-auto py-8 max-w-3xl space-y-4">
        <p>找不到 member id「{memberId}」</p>
        <Button asChild variant="outline"><Link to="/admin/member">回成員列表</Link></Button>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 max-w-3xl space-y-4">
      <div className="text-sm">
        <Link to="/admin/member" className="text-muted-foreground hover:underline">← 回成員</Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-xl">{member.email}</CardTitle>
          <CardDescription className="font-mono text-xs">{member.id}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
            <div><span className="text-muted-foreground">登入方式：</span>{member.provider}</div>
            <div>
              <span className="text-muted-foreground">狀態：</span>
              <Badge variant={member.status === "active" ? "default" : "secondary"}>
                {member.status}
              </Badge>
            </div>
            <div>
              <span className="text-muted-foreground">管理員：</span>
              {member.is_admin ? <Badge>是</Badge> : <span className="text-muted-foreground">否</span>}
            </div>
            <div className="col-span-3 text-xs text-muted-foreground">
              建立於 {new Date(member.created_at).toLocaleString("zh-TW")}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Tag</CardTitle>
          <CardDescription>到「成員」列表 inline 編輯；此處檢視用</CardDescription>
        </CardHeader>
        <CardContent>
          {tagsQuery.data?.length === 0 ? (
            <p className="text-sm text-muted-foreground">無 tag</p>
          ) : (
            <div className="flex flex-wrap gap-1">
              {tagsQuery.data?.map((t) => (
                <Badge key={t.tag} variant="secondary" className="text-xs">
                  <Link to={`/admin/tag/${t.tag}`} className="hover:underline">{t.tag}</Link>
                  {t.source === "auto" && (
                    <span
                      className="ml-1 rounded bg-primary/15 px-1 text-[10px] text-primary"
                      title="由自動標籤規則貼上"
                    >自動</span>
                  )}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">可用 Model</CardTitle>
          <CardDescription>
            該 member 通過 credential gate ∩ access policy 後實際看得到的清單
          </CardDescription>
        </CardHeader>
        <CardContent>
          {visibleQuery.isLoading && <p className="text-sm">載入中…</p>}
          {visibleQuery.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">該 member 目前看不到任何 model</p>
          )}
          {(visibleQuery.data ?? []).length > 0 && (
            <ul className="text-sm space-y-1">
              {visibleQuery.data?.map((m) => (
                <li key={m.slug}>
                  <Link to={`/admin/model/${m.slug}`} className="font-mono text-xs text-primary hover:underline">
                    {m.slug}
                  </Link>
                  <span className="ml-2 text-muted-foreground">{m.display_name}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-3">
            <VisibilityDiagnose memberId={memberId} compact />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <div>
              <CardTitle className="text-lg">分配（Allocations）</CardTitle>
              <CardDescription>該成員的所有分配（model 授權）；在此直接建立與撤回</CardDescription>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              {revokedCount > 0 && (
                <div className="flex items-center gap-2">
                  <Switch id="member-show-revoked" checked={showRevoked} onCheckedChange={setShowRevoked} />
                  <Label htmlFor="member-show-revoked" className="text-sm">
                    含已撤回（{revokedCount}）
                  </Label>
                </div>
              )}
              <Button size="sm" onClick={() => setCreateOpen(true)}>
                新增分配
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {memberAllocs.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {!showRevoked && revokedCount > 0
                ? `無進行中的分配（另有 ${revokedCount} 筆已撤回，開啟「含已撤回」可查看）。`
                : "此成員還沒有任何分配。按「新增分配」發一張綁定該成員的憑證。"}
            </p>
          ) : (
            <Table className="responsive-table">
              <TableHeader>
                <TableRow>
                  <TableHead>模型</TableHead>
                  <TableHead>狀態</TableHead>
                  <TableHead>配額</TableHead>
                  <TableHead>Token</TableHead>
                  <TableHead className="text-right">動作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {memberAllocs.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="text-xs" data-label="模型">
                      <div className="min-w-0">
                        {a.display_name && <div className="font-medium">{a.display_name}</div>}
                        <div className="font-mono text-muted-foreground break-all">{a.resource_model}</div>
                      </div>
                    </TableCell>
                    <TableCell data-label="狀態">
                      <Badge variant={a.status === "active" ? "default" : "secondary"}>{a.status}</Badge>
                    </TableCell>
                    <TableCell data-label="配額">{a.quota_tokens_per_month ?? "無限額"}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground" data-label="Token">{a.token_prefix}…</TableCell>
                    <TableCell className="text-right space-x-2" data-label="動作">
                      {a.status === "active" && (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => pauseResumeMut.mutate({ id: a.id, action: "pause" })}
                          >
                            暫停
                          </Button>
                          <Button size="sm" variant="destructive" onClick={() => setRevokeTarget(a)}>
                            撤回
                          </Button>
                        </>
                      )}
                      {a.status === "paused" && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => pauseResumeMut.mutate({ id: a.id, action: "resume" })}
                        >
                          恢復
                        </Button>
                      )}
                      {a.status === "revoked" && (
                        <span className="text-xs text-muted-foreground">已撤回</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <AdminMemberCredentials memberId={memberId} />

      <CreateAllocationDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        memberId={memberId}
        memberEmail={member.email}
        onCreated={(token) => {
          queryClient.invalidateQueries({ queryKey: ["admin", "allocations"] });
          setTokenDialog(token);
        }}
      />

      {/* one-time token reveal */}
      <Dialog open={!!tokenDialog} onOpenChange={(open) => !open && setTokenDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>分配已建立 — 此 token 只顯示一次</DialogTitle>
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

      {/* revoke confirm */}
      <AlertDialog open={!!revokeTarget} onOpenChange={(open) => !open && setRevokeTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>撤回這筆分配？</AlertDialogTitle>
            <AlertDialogDescription>
              撤回後 token「{revokeTarget?.token_prefix}…」的後續呼叫會立即被拒絕，無法復原。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={() => revokeTarget && revokeMut.mutate(revokeTarget.id)}>
              撤回
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function CreateAllocationDialog({
  open,
  onOpenChange,
  memberId,
  memberEmail,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  memberId: string;
  memberEmail: string;
  onCreated: (token: string) => void;
}) {
  const { toast } = useToast();
  const [model, setModel] = React.useState("");
  const [quota, setQuota] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      setModel("");
      setQuota("");
    }
  }, [open]);

  const catalogQuery = useQuery<Array<{ slug: string; display_name: string }>, ApiError>({
    queryKey: ["admin", "catalog-models-admin"],
    queryFn: () =>
      api<Array<{ slug: string; display_name: string }>>("/admin/catalog/models"),
    enabled: open,
  });

  const submit = async () => {
    setSubmitting(true);
    try {
      const created = await api<{ token: string }>("/admin/allocations", {
        method: "POST",
        body: JSON.stringify({
          member_id: memberId,
          resource_model: model,
          quota_tokens_per_month: quota.trim() === "" ? undefined : Number(quota),
        }),
      });
      onCreated(created.token);
      onOpenChange(false);
    } catch (err) {
      toast({ title: "建立失敗", description: (err as ApiError).message, variant: "destructive" });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新增分配</DialogTitle>
          <DialogDescription>發一張綁定 {memberEmail} 的憑證。</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label>模型</Label>
            <Select value={model || undefined} onValueChange={setModel}>
              <SelectTrigger className="mt-1">
                <SelectValue
                  placeholder={
                    catalogQuery.isLoading
                      ? "載入 catalog…"
                      : (catalogQuery.data?.length ?? 0) === 0
                        ? "catalog 是空的；先到 Model → Catalog 管理加入"
                        : "選擇 model"
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {catalogQuery.data?.map((m) => (
                  <SelectItem key={m.slug} value={m.slug}>
                    {m.slug}
                    <span className="text-muted-foreground ml-1">（{m.display_name}）</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="alloc-quota">月度配額 tokens（可選；空白＝無限額）</Label>
            <Input
              id="alloc-quota"
              type="number"
              className="mt-1"
              value={quota}
              onChange={(e) => setQuota(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button disabled={!model || submitting} onClick={() => void submit()}>建立</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
