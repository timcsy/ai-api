import * as React from "react";
import { Link } from "react-router-dom";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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

type MatcherType =
  | "email_localpart_regex"
  | "email_suffix"
  | "email_domain"
  | "always";

interface TagRule {
  id: string;
  order_index: number;
  matcher_type: MatcherType;
  pattern: string;
  tag: string;
  enabled: boolean;
  created_at: string;
  created_by: string;
}

interface RuleMatch {
  matched: boolean;
  rule_id: string | null;
  tag: string | null;
  matcher_type: MatcherType | null;
}

const MATCHER_LABELS: Record<MatcherType, string> = {
  email_localpart_regex: "@ 前段格式比對（學號 / 帳號）",
  email_suffix: "Email 結尾比對（單位 / 子網域）",
  email_domain: "Email 網域完全比對",
  always: "其他全部（Fallback）",
};

const MATCHER_HINTS: Record<MatcherType, string> = {
  email_localpart_regex:
    "比對 email「@ 前面」那段的格式。例：b10901234@school.edu → 比對 b10901234。學生學號是固定格式、老師多是姓名，可用這個區分「同校」的學生 vs 老師。",
  email_suffix:
    "比對 email 是否以某段字串結尾。例：以 @students.school.edu 結尾 → 命中該子網域所有人。",
  email_domain:
    "比對 @ 後面的網域是否完全相同。例：school.edu（注意 sub.school.edu 不算）。",
  always:
    "一定命中。當作「以上規則都不符」時的預設，請放在最後一條（例如 → teacher）。",
};

const RULES_KEY = ["admin", "tag-rules"];

export function AdminTagRulesPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [editing, setEditing] = React.useState<TagRule | null>(null);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [deleteConfirm, setDeleteConfirm] = React.useState<TagRule | null>(null);

  // form state (shared by create + edit)
  const [matcher, setMatcher] = React.useState<MatcherType>("email_localpart_regex");
  const [pattern, setPattern] = React.useState("");
  const [tag, setTag] = React.useState("");

  // test email box
  const [testEmail, setTestEmail] = React.useState("");
  const [testResult, setTestResult] = React.useState<RuleMatch | null>(null);

  const rulesQuery = useQuery<TagRule[], ApiError>({
    queryKey: RULES_KEY,
    queryFn: () => api<TagRule[]>("/admin/tag-rules"),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: RULES_KEY });

  const resetForm = () => {
    setMatcher("email_localpart_regex");
    setPattern("");
    setTag("");
  };

  const createMut = useMutation<TagRule, ApiError, { matcher_type: MatcherType; pattern: string; tag: string }>({
    mutationFn: (data) => api<TagRule>("/admin/tag-rules", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => {
      toast({ title: "規則已建立" });
      setCreateOpen(false);
      resetForm();
      invalidate();
    },
    onError: (e) => toast({ title: "建立失敗", description: e.message, variant: "destructive" }),
  });

  const updateMut = useMutation<TagRule, ApiError, { id: string; body: Partial<TagRule> }>({
    mutationFn: ({ id, body }) =>
      api<TagRule>(`/admin/tag-rules/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => {
      toast({ title: "規則已更新" });
      setEditing(null);
      resetForm();
      invalidate();
    },
    onError: (e) => toast({ title: "更新失敗", description: e.message, variant: "destructive" }),
  });

  const deleteMut = useMutation<void, ApiError, string>({
    mutationFn: (id) => api(`/admin/tag-rules/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast({ title: "規則已刪除" });
      setDeleteConfirm(null);
      invalidate();
    },
    onError: (e) => toast({ title: "刪除失敗", description: e.message, variant: "destructive" }),
  });

  const reorderMut = useMutation<TagRule[], ApiError, string[]>({
    mutationFn: (order) =>
      api<TagRule[]>("/admin/tag-rules/reorder", { method: "POST", body: JSON.stringify({ order }) }),
    onSuccess: () => invalidate(),
    onError: (e) => toast({ title: "排序失敗", description: e.message, variant: "destructive" }),
  });

  const testMut = useMutation<RuleMatch, ApiError, string>({
    mutationFn: (email) =>
      api<RuleMatch>("/admin/tag-rules/test", { method: "POST", body: JSON.stringify({ email }) }),
    onSuccess: (r) => setTestResult(r),
    onError: (e) => toast({ title: "測試失敗", description: e.message, variant: "destructive" }),
  });

  const rules = rulesQuery.data ?? [];

  const move = (index: number, dir: -1 | 1) => {
    const target = index + dir;
    if (target < 0 || target >= rules.length) return;
    const ids = rules.map((r) => r.id);
    const moved = ids[index];
    if (moved === undefined) return;
    ids.splice(index, 1);
    ids.splice(target, 0, moved);
    reorderMut.mutate(ids);
  };

  const openCreate = () => {
    resetForm();
    setCreateOpen(true);
  };

  const openEdit = (rule: TagRule) => {
    setMatcher(rule.matcher_type);
    // strip the auto-anchor wrapper for display so admins edit what they typed
    setPattern(rule.pattern);
    setTag(rule.tag);
    setEditing(rule);
  };

  const patternNeeded = matcher !== "always";

  return (
    <div className="container mx-auto py-8 max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">自動標籤規則</h1>
          <p className="text-sm text-muted-foreground mt-1">
            新成員<strong>首次註冊</strong>時，系統由上而下評估規則，套用<strong>第一條命中</strong>的標籤。
            <Link to="/admin/tag" className="ml-1 underline">← 回標籤管理</Link>
          </p>
        </div>
        <Button onClick={openCreate}>新增規則</Button>
      </div>

      <Table className="responsive-table">
        <TableHeader>
          <TableRow>
            <TableHead className="w-20">順序</TableHead>
            <TableHead>條件</TableHead>
            <TableHead>貼上標籤</TableHead>
            <TableHead>啟用</TableHead>
            <TableHead className="text-right">動作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rulesQuery.isLoading && (
            <TableRow><TableCell colSpan={5} className="text-muted-foreground">載入中…</TableCell></TableRow>
          )}
          {rules.length === 0 && !rulesQuery.isLoading && (
            <TableRow>
              <TableCell colSpan={5} className="text-muted-foreground">
                還沒有規則。按「新增規則」建立第一條（例如學號 regex → student）。
              </TableCell>
            </TableRow>
          )}
          {rules.map((rule, i) => (
            <TableRow key={rule.id} className={rule.enabled ? "" : "opacity-50"}>
              <TableCell data-label="順序">
                <div className="flex items-center gap-1">
                  <span className="tabular-nums">{i + 1}</span>
                  <div className="flex flex-col">
                    <button
                      aria-label="上移"
                      disabled={i === 0 || reorderMut.isPending}
                      onClick={() => move(i, -1)}
                      className="text-xs disabled:opacity-30"
                    >▲</button>
                    <button
                      aria-label="下移"
                      disabled={i === rules.length - 1 || reorderMut.isPending}
                      onClick={() => move(i, 1)}
                      className="text-xs disabled:opacity-30"
                    >▼</button>
                  </div>
                </div>
              </TableCell>
              <TableCell data-label="條件">
                <div className="min-w-0">
                  <div className="text-sm">{MATCHER_LABELS[rule.matcher_type]}</div>
                  {rule.matcher_type !== "always" && (
                    <code className="text-xs text-muted-foreground break-all">{rule.pattern}</code>
                  )}
                </div>
              </TableCell>
              <TableCell data-label="貼上標籤"><Badge variant="secondary">{rule.tag}</Badge></TableCell>
              <TableCell data-label="啟用">
                <Switch
                  checked={rule.enabled}
                  onCheckedChange={(v) => updateMut.mutate({ id: rule.id, body: { enabled: v } })}
                />
              </TableCell>
              <TableCell className="text-right space-x-2" data-label="動作">
                <Button size="sm" variant="outline" onClick={() => openEdit(rule)}>編輯</Button>
                <Button size="sm" variant="destructive" onClick={() => setDeleteConfirm(rule)}>刪除</Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {/* Test email box */}
      <div className="border rounded-md p-4 space-y-3">
        <Label htmlFor="test-email" className="font-semibold">測試 email</Label>
        <p className="text-xs text-muted-foreground">輸入一個 email，預覽會命中哪條規則、貼哪個標籤（不會建立成員）。</p>
        <div className="flex gap-2">
          <Input
            id="test-email"
            placeholder="b10901234@school.edu"
            value={testEmail}
            onChange={(e) => setTestEmail(e.target.value)}
          />
          <Button
            variant="outline"
            disabled={!testEmail || testMut.isPending}
            onClick={() => testMut.mutate(testEmail.trim())}
          >測試</Button>
        </div>
        {testResult && (
          <div className="text-sm">
            {testResult.matched ? (
              <span>命中 → 貼上 <Badge variant="secondary">{testResult.tag}</Badge></span>
            ) : (
              <span className="text-muted-foreground">沒有任何規則命中（不會貼自動標籤）</span>
            )}
          </div>
        )}
      </div>

      {/* Create / edit dialog */}
      <Dialog
        open={createOpen || editing !== null}
        onOpenChange={(v) => {
          if (!v) {
            setCreateOpen(false);
            setEditing(null);
            resetForm();
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "編輯規則" : "新增規則"}</DialogTitle>
            <DialogDescription>
              選擇比對方式與要貼的標籤。regex 會在儲存時做安全檢查（拒絕高風險樣式）。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>比對方式</Label>
              <Select value={matcher} onValueChange={(v) => setMatcher(v as MatcherType)}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(Object.keys(MATCHER_LABELS) as MatcherType[]).map((m) => (
                    <SelectItem key={m} value={m}>{MATCHER_LABELS[m]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="mt-2 rounded-md bg-muted/60 p-2 text-xs leading-relaxed text-muted-foreground">
                {MATCHER_HINTS[matcher]}
              </p>
            </div>
            {patternNeeded && (
              <div>
                <Label htmlFor="pattern">
                  {matcher === "email_localpart_regex" ? "Regex（local-part）"
                    : matcher === "email_suffix" ? "結尾字串" : "網域"}
                </Label>
                <Input
                  id="pattern"
                  className="mt-1 font-mono"
                  placeholder={
                    matcher === "email_localpart_regex" ? "[a-z]{0,2}\\d{6,}"
                      : matcher === "email_suffix" ? "@students.school.edu" : "school.edu"
                  }
                  value={pattern}
                  onChange={(e) => setPattern(e.target.value)}
                />
              </div>
            )}
            <div>
              <Label htmlFor="rule-tag">貼上的標籤</Label>
              <Input
                id="rule-tag"
                className="mt-1"
                placeholder="student / teacher ..."
                value={tag}
                onChange={(e) => setTag(e.target.value)}
              />
              <p className="text-xs text-muted-foreground mt-1">格式：小寫字母開頭，後接小寫字母 / 數字 / dash / underscore</p>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => { setCreateOpen(false); setEditing(null); resetForm(); }}
            >取消</Button>
            <Button
              disabled={!tag || (patternNeeded && !pattern) || createMut.isPending || updateMut.isPending}
              onClick={() => {
                if (editing) {
                  updateMut.mutate({
                    id: editing.id,
                    body: { matcher_type: matcher, pattern: patternNeeded ? pattern : "", tag },
                  });
                } else {
                  createMut.mutate({ matcher_type: matcher, pattern: patternNeeded ? pattern : "", tag });
                }
              }}
            >{editing ? "儲存" : "建立"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleteConfirm !== null} onOpenChange={(v) => !v && setDeleteConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>刪除規則？</AlertDialogTitle>
            <AlertDialogDescription>
              已自動貼上的標籤不會被移除；只是之後新成員不再套用此規則。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={() => deleteConfirm && deleteMut.mutate(deleteConfirm.id)}>刪除</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
