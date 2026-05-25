import * as React from "react";
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

interface TagSummary {
  tag: string;
  member_count: number;
}

interface AdminMember {
  id: string;
  email: string;
  status: string;
}

export function AdminTagsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [bulkOpen, setBulkOpen] = React.useState(false);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [newTag, setNewTag] = React.useState("");
  const [deleteConfirm, setDeleteConfirm] = React.useState<TagSummary | null>(null);

  const tagsQuery = useQuery<TagSummary[], ApiError>({
    queryKey: ["admin", "tags"],
    queryFn: () => api<TagSummary[]>("/admin/tags"),
  });

  const membersQuery = useQuery<AdminMember[], ApiError>({
    queryKey: ["admin", "members"],
    queryFn: () => api<AdminMember[]>("/admin/members"),
    enabled: bulkOpen,
  });

  const [bulkTag, setBulkTag] = React.useState("");
  const [selectedMembers, setSelectedMembers] = React.useState<Set<string>>(new Set());

  const bulkMut = useMutation<
    { tag: string; applied_count: number; skipped_count: number },
    ApiError,
    { tag: string; member_ids: string[] }
  >({
    mutationFn: (data) =>
      api(`/admin/tags/bulk-apply`, { method: "POST", body: JSON.stringify(data) }),
    onSuccess: (result) => {
      toast({
        title: `已套用 tag "${result.tag}"`,
        description: `新增 ${result.applied_count} 人，已有 tag 跳過 ${result.skipped_count} 人`,
      });
      setBulkOpen(false);
      setBulkTag("");
      setSelectedMembers(new Set());
      queryClient.invalidateQueries({ queryKey: ["admin", "tags"] });
    },
    onError: (e) => toast({ title: "批次套用失敗", description: e.message, variant: "destructive" }),
  });

  const createMut = useMutation<TagSummary, ApiError, string>({
    mutationFn: (tag) =>
      api<TagSummary>("/admin/tags", { method: "POST", body: JSON.stringify({ tag }) }),
    onSuccess: (r) => {
      toast({ title: `已建立 tag「${r.tag}」`, description: "現在可在 Model 存取頁套用此 tag" });
      setCreateOpen(false);
      setNewTag("");
      queryClient.invalidateQueries({ queryKey: ["admin", "tags"] });
    },
    onError: (e) => toast({ title: "建立失敗", description: e.message, variant: "destructive" }),
  });

  const deleteMut = useMutation<void, ApiError, string>({
    mutationFn: (tag) =>
      api(`/admin/tags/${encodeURIComponent(tag)}`, { method: "DELETE" }),
    onSuccess: () => {
      toast({ title: "Tag 已從所有成員移除" });
      setDeleteConfirm(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "tags"] });
    },
    onError: (e) => toast({ title: "刪除失敗", description: e.message, variant: "destructive" }),
  });

  return (
    <div className="container mx-auto py-8 max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Tag 管理</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setCreateOpen(true)}>建立 Tag</Button>
          <Button onClick={() => setBulkOpen(true)}>批次貼標</Button>
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        Tag 用於控制 model 對成員的可見性。在「Model 存取」頁設定哪些 tag 可使用哪個 model。
      </p>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Tag</TableHead>
            <TableHead>使用人數</TableHead>
            <TableHead className="text-right">動作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tagsQuery.isLoading && (
            <TableRow>
              <TableCell colSpan={3} className="text-muted-foreground">載入中…</TableCell>
            </TableRow>
          )}
          {tagsQuery.data?.length === 0 && (
            <TableRow>
              <TableCell colSpan={3} className="text-muted-foreground">
                目前沒有任何 tag；按「批次貼標」開始。
              </TableCell>
            </TableRow>
          )}
          {tagsQuery.data?.map((t) => (
            <TableRow key={t.tag}>
              <TableCell>
                <Badge variant="secondary">{t.tag}</Badge>
              </TableCell>
              <TableCell>{t.member_count}</TableCell>
              <TableCell className="text-right">
                <Button size="sm" variant="destructive" onClick={() => setDeleteConfirm(t)}>
                  全域刪除
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {/* Bulk apply dialog */}
      <Dialog open={bulkOpen} onOpenChange={setBulkOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>批次貼 Tag</DialogTitle>
            <DialogDescription>
              一次為多名成員加上同一個 tag。已有此 tag 的成員會跳過。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="bulk-tag">Tag 名稱</Label>
              <Input
                id="bulk-tag"
                placeholder="eng / pm / contractor ..."
                value={bulkTag}
                onChange={(e) => setBulkTag(e.target.value)}
                className="mt-1"
              />
              <p className="text-xs text-muted-foreground mt-1">
                格式：小寫字母 / 數字 / dash / underscore，開頭為字母
              </p>
            </div>
            <div>
              <Label>選擇成員（{selectedMembers.size} 已選）</Label>
              <div className="border rounded-md max-h-64 overflow-y-auto mt-1">
                {membersQuery.data?.map((m) => (
                  <label
                    key={m.id}
                    className="flex items-center gap-2 p-2 hover:bg-muted cursor-pointer text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={selectedMembers.has(m.id)}
                      onChange={(e) => {
                        const next = new Set(selectedMembers);
                        if (e.target.checked) next.add(m.id);
                        else next.delete(m.id);
                        setSelectedMembers(next);
                      }}
                    />
                    <span>{m.email}</span>
                    {m.status !== "active" && (
                      <Badge variant="outline" className="text-xs">{m.status}</Badge>
                    )}
                  </label>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBulkOpen(false)}>取消</Button>
            <Button
              disabled={!bulkTag || selectedMembers.size === 0 || bulkMut.isPending}
              onClick={() =>
                bulkMut.mutate({ tag: bulkTag, member_ids: Array.from(selectedMembers) })
              }
            >
              套用
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create empty tag dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>建立 Tag</DialogTitle>
            <DialogDescription>
              先定義 tag 名稱（之後可在 Model 存取頁設定哪些 model 允許 / 禁止此 tag）。
              成員可在批次貼標 dialog 套用此 tag。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="new-tag">Tag 名稱</Label>
            <Input
              id="new-tag"
              placeholder="eng / pm / contractor ..."
              value={newTag}
              onChange={(e) => setNewTag(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              格式：小寫字母開頭，後接小寫字母 / 數字 / dash / underscore
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>取消</Button>
            <Button
              disabled={!newTag || createMut.isPending}
              onClick={() => createMut.mutate(newTag.trim())}
            >
              建立
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={deleteConfirm !== null}
        onOpenChange={(v) => !v && setDeleteConfirm(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>從所有成員移除 tag「{deleteConfirm?.tag}」？</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteConfirm?.member_count} 名成員會失去這個 tag；如有 model 依賴它做存取控制，他們將立即失去存取權。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteConfirm && deleteMut.mutate(deleteConfirm.tag)}
            >
              全域刪除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
