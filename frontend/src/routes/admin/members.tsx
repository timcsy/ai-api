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
}

const createSchema = z
  .object({
    email: z.string().email("email 格式錯"),
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
  const [confirm, setConfirm] = React.useState<
    | { kind: "demote"; member: AdminMember }
    | { kind: "promote"; member: AdminMember }
    | { kind: "disable"; member: AdminMember }
    | { kind: "enable"; member: AdminMember }
    | { kind: "delete"; member: AdminMember }
    | null
  >(null);

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
        <Button onClick={() => setCreateOpen(true)}>新增成員</Button>
      </div>

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
            {query.data.map((m) => (
              <TableRow key={m.id}>
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
                  <MemberTagsCell memberId={m.id} />
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
            {query.data.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  尚無成員
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
            <AlertDialogTitle>確認操作</AlertDialogTitle>
            <AlertDialogDescription>
              {confirm && `對 ${confirm.member.email} 執行：${confirm.kind}`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={() => void performConfirmed()}>確認</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function MemberTagsCell({ memberId }: { memberId: string }) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [open, setOpen] = React.useState(false);
  const [newTag, setNewTag] = React.useState("");

  const tagsQuery = useQuery<string[], ApiError>({
    queryKey: ["admin", "members", memberId, "tags"],
    queryFn: () => api<string[]>(`/admin/members/${memberId}/tags`),
  });

  const addMut = useMutation<string[], ApiError, string>({
    mutationFn: (tag) =>
      api<string[]>(`/admin/members/${memberId}/tags`, {
        method: "POST",
        body: JSON.stringify({ tags: [tag] }),
      }),
    onSuccess: () => {
      setNewTag("");
      queryClient.invalidateQueries({ queryKey: ["admin", "members", memberId, "tags"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "tags"] });
    },
    onError: (e) => toast({ title: "加標籤失敗", description: e.message, variant: "destructive" }),
  });

  const removeMut = useMutation<void, ApiError, string>({
    mutationFn: (tag) =>
      api<void>(`/admin/members/${memberId}/tags?tag=${encodeURIComponent(tag)}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "members", memberId, "tags"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "tags"] });
    },
    onError: (e) => toast({ title: "移除標籤失敗", description: e.message, variant: "destructive" }),
  });

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {tagsQuery.data?.map((tag) => (
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
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input type="email" {...field} />
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
