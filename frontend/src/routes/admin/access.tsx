import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/use-toast";
import { ApiError, api } from "@/lib/api-client";

interface AutoRegisterRule {
  id: string;
  rule_type: "email_domain";
  pattern: string;
  enabled: boolean;
  created_at: string;
  created_by: string;
  note: string | null;
}

interface SourceRestriction {
  id: string;
  cidr: string;
  enabled: boolean;
  created_at: string;
  created_by: string;
  note: string | null;
}

const fmtDate = (iso: string) => new Date(iso).toLocaleString("zh-TW");

export function AdminAccessPage() {
  return (
    <div className="container mx-auto py-8 max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">存取規則</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          管理「誰可以登入」與「從哪裡可以登入」。已有管理員後，登入授權完全由這裡與「成員」決定；
          email 白名單僅在尚無管理員的 bootstrap 階段有效，之後即停用。
        </p>
      </div>
      <RulesSection />
      <SourceRestrictionsSection />
    </div>
  );
}

function RulesSection() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [open, setOpen] = React.useState(false);
  const q = useQuery<AutoRegisterRule[], ApiError>({
    queryKey: ["admin", "access", "rules"],
    queryFn: () => api<AutoRegisterRule[]>("/admin/rules"),
  });
  const del = useMutation<unknown, ApiError, string>({
    mutationFn: (id) => api(`/admin/rules/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "access", "rules"] });
      toast({ title: "已刪除" });
    },
    onError: (e) => toast({ title: "刪除失敗", description: e.message, variant: "destructive" }),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-lg">自動註冊規則</CardTitle>
            <CardDescription>
              符合規則的 email 首次以 Google 登入時自動建立成員。例：填入網域 <code>example.com</code>，
              則該網域全部同事都能登入並自動成為成員。
            </CardDescription>
          </div>
          <Button className="shrink-0" onClick={() => setOpen(true)}>新增規則</Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="pl-6">類型</TableHead>
              <TableHead>條件</TableHead>
              <TableHead>狀態</TableHead>
              <TableHead>備註</TableHead>
              <TableHead>建立時間</TableHead>
              <TableHead className="pr-6 text-right">動作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {q.isLoading && (
              <TableRow><TableCell colSpan={6} className="pl-6 text-muted-foreground">載入中…</TableCell></TableRow>
            )}
            {q.data?.length === 0 && !q.isLoading && (
              <TableRow><TableCell colSpan={6} className="pl-6 py-8 text-center text-muted-foreground">
                尚未設定任何規則（這代表只有「成員」名單裡的人能登入）
              </TableCell></TableRow>
            )}
            {q.data?.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="pl-6">{r.rule_type === "email_domain" ? "Email 網域" : r.rule_type}</TableCell>
                <TableCell><code className="font-mono">{r.pattern}</code></TableCell>
                <TableCell>
                  {r.enabled
                    ? <Badge>啟用</Badge>
                    : <Badge variant="outline" className="text-muted-foreground">停用</Badge>}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{r.note || "—"}</TableCell>
                <TableCell className="text-xs text-muted-foreground tabular-nums">{fmtDate(r.created_at)}</TableCell>
                <TableCell className="pr-6 text-right">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => { if (confirm(`確定刪除規則 ${r.pattern}？`)) del.mutate(r.id); }}
                    disabled={del.isPending}
                  >刪除</Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>

      <AddRuleDialog open={open} onOpenChange={setOpen} onCreated={() => {
        queryClient.invalidateQueries({ queryKey: ["admin", "access", "rules"] });
        toast({ title: "已新增規則" });
        setOpen(false);
      }} />
    </Card>
  );
}

function AddRuleDialog({ open, onOpenChange, onCreated }: {
  open: boolean; onOpenChange: (o: boolean) => void; onCreated: () => void;
}) {
  const { toast } = useToast();
  const [pattern, setPattern] = React.useState("");
  const [note, setNote] = React.useState("");
  const [enabled, setEnabled] = React.useState(true);
  React.useEffect(() => { if (open) { setPattern(""); setNote(""); setEnabled(true); } }, [open]);
  const mut = useMutation<unknown, ApiError, void>({
    mutationFn: () => api("/admin/rules", {
      method: "POST",
      body: JSON.stringify({
        rule_type: "email_domain",
        pattern: pattern.trim().toLowerCase(),
        enabled,
        note: note || null,
      }),
    }),
    onSuccess: () => onCreated(),
    onError: (e) => toast({ title: "新增失敗", description: e.message, variant: "destructive" }),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新增自動註冊規則</DialogTitle>
          <DialogDescription>
            符合此規則的 email 首次以 Google 登入時可自動成為成員。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label htmlFor="r-pattern">Email 網域</Label>
            <Input id="r-pattern" className="mt-1 font-mono" placeholder="example.com"
              value={pattern} onChange={(e) => setPattern(e.target.value)} />
            <p className="text-xs text-muted-foreground mt-1">只填網域部分，不要含 @ 或 https://。</p>
          </div>
          <div>
            <Label htmlFor="r-note">備註（可選）</Label>
            <Input id="r-note" className="mt-1" placeholder="例如：校內同事"
              value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          <div className="flex items-center gap-2">
            <Switch id="r-enabled" checked={enabled} onCheckedChange={setEnabled} />
            <Label htmlFor="r-enabled" className="cursor-pointer">啟用</Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button disabled={!pattern.trim() || mut.isPending} onClick={() => mut.mutate()}>
            {mut.isPending ? "新增中…" : "新增"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SourceRestrictionsSection() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [open, setOpen] = React.useState(false);
  const q = useQuery<SourceRestriction[], ApiError>({
    queryKey: ["admin", "access", "source-restrictions"],
    queryFn: () => api<SourceRestriction[]>("/admin/source-restrictions"),
  });
  const del = useMutation<unknown, ApiError, string>({
    mutationFn: (id) => api(`/admin/source-restrictions/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "access", "source-restrictions"] });
      toast({ title: "已刪除" });
    },
    onError: (e) => toast({ title: "刪除失敗", description: e.message, variant: "destructive" }),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-lg">來源限制（IP / 網段）</CardTitle>
            <CardDescription>
              限定可登入的網段。**未設定任何規則時 = 不限制**；設定後，登入請求的來源 IP 必須符合至少一條。
            </CardDescription>
          </div>
          <Button className="shrink-0" onClick={() => setOpen(true)}>新增限制</Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="pl-6">CIDR</TableHead>
              <TableHead>狀態</TableHead>
              <TableHead>備註</TableHead>
              <TableHead>建立時間</TableHead>
              <TableHead className="pr-6 text-right">動作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {q.isLoading && (
              <TableRow><TableCell colSpan={5} className="pl-6 text-muted-foreground">載入中…</TableCell></TableRow>
            )}
            {q.data?.length === 0 && !q.isLoading && (
              <TableRow><TableCell colSpan={5} className="pl-6 py-8 text-center text-muted-foreground">
                尚未設定（不限制 IP）
              </TableCell></TableRow>
            )}
            {q.data?.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="pl-6"><code className="font-mono">{r.cidr}</code></TableCell>
                <TableCell>
                  {r.enabled
                    ? <Badge>啟用</Badge>
                    : <Badge variant="outline" className="text-muted-foreground">停用</Badge>}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{r.note || "—"}</TableCell>
                <TableCell className="text-xs text-muted-foreground tabular-nums">{fmtDate(r.created_at)}</TableCell>
                <TableCell className="pr-6 text-right">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => { if (confirm(`確定刪除 ${r.cidr}？`)) del.mutate(r.id); }}
                    disabled={del.isPending}
                  >刪除</Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>

      <AddRestrictionDialog open={open} onOpenChange={setOpen} onCreated={() => {
        queryClient.invalidateQueries({ queryKey: ["admin", "access", "source-restrictions"] });
        toast({ title: "已新增限制" });
        setOpen(false);
      }} />
    </Card>
  );
}

function AddRestrictionDialog({ open, onOpenChange, onCreated }: {
  open: boolean; onOpenChange: (o: boolean) => void; onCreated: () => void;
}) {
  const { toast } = useToast();
  const [cidr, setCidr] = React.useState("");
  const [note, setNote] = React.useState("");
  const [enabled, setEnabled] = React.useState(true);
  React.useEffect(() => { if (open) { setCidr(""); setNote(""); setEnabled(true); } }, [open]);
  const mut = useMutation<unknown, ApiError, void>({
    mutationFn: () => api("/admin/source-restrictions", {
      method: "POST",
      body: JSON.stringify({ cidr: cidr.trim(), enabled, note: note || null }),
    }),
    onSuccess: () => onCreated(),
    onError: (e) => toast({ title: "新增失敗", description: e.message, variant: "destructive" }),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新增來源限制</DialogTitle>
          <DialogDescription>
            以 CIDR 形式填寫允許的網段（IPv4 或 IPv6）。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label htmlFor="sr-cidr">CIDR</Label>
            <Input id="sr-cidr" className="mt-1 font-mono" placeholder="203.0.113.0/24"
              value={cidr} onChange={(e) => setCidr(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="sr-note">備註（可選）</Label>
            <Input id="sr-note" className="mt-1" placeholder="例如：校園網路"
              value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          <div className="flex items-center gap-2">
            <Switch id="sr-enabled" checked={enabled} onCheckedChange={setEnabled} />
            <Label htmlFor="sr-enabled" className="cursor-pointer">啟用</Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button disabled={!cidr.trim() || mut.isPending} onClick={() => mut.mutate()}>
            {mut.isPending ? "新增中…" : "新增"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
