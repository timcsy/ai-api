import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/use-toast";
import { ApiError, api } from "@/lib/api-client";

interface NotificationConfigResponse {
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_password_fingerprint: string;
  sender_email: string;
  sender_name: string;
  recipients: string[];
  enabled: boolean;
  status: "pending_test" | "verified" | "credentials_invalid";
  last_test_at: string | null;
  last_test_outcome: string | null;
  last_test_error: string | null;
}

interface TestSendResponse {
  outcome: string;
  message: string;
  smtp_response_code: number | null;
  latency_ms: number;
}

interface NotificationRecord {
  id: string;
  event_type: string;
  outcome: string;
  recipients: string[];
  per_recipient_status: Record<string, string>;
  subject: string;
  error_message: string | null;
  smtp_response_code: number | null;
  created_at: string;
  bucket_event_count: number | null;
}

interface HistoryResponse {
  rows: NotificationRecord[];
  next_cursor: string | null;
}

const OUTCOME_LABEL: Record<string, string> = {
  sent: "已寄出",
  suppressed: "已合併（去重）",
  skipped_disabled: "略過（停用）",
  skipped_no_recipients: "略過（無收件人）",
  send_failed_auth: "失敗（驗證）",
  send_failed_connect: "失敗（連線）",
  send_failed_sender: "失敗（寄件者被拒）",
  send_failed_all_recipients: "失敗（全部收件人被拒）",
  send_failed_unknown: "失敗（未知）",
  test_sent: "測試成功",
};

function outcomeLabel(outcome: string): string {
  return OUTCOME_LABEL[outcome] ?? outcome;
}

const STATUS_LABEL: Record<NotificationConfigResponse["status"], { text: string; variant: "default" | "outline" | "destructive" }> = {
  pending_test: { text: "待測試", variant: "outline" },
  verified: { text: "✓ 已驗證", variant: "default" },
  credentials_invalid: { text: "⚠ 憑證無效", variant: "destructive" },
};

export function AdminNotificationsPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const configQuery = useQuery<NotificationConfigResponse | null, ApiError>({
    queryKey: ["admin", "notifications", "config"],
    queryFn: async () => {
      const res = await fetch("/admin/notifications/config", {
        headers: { Accept: "application/json" },
      });
      if (res.status === 204) return null;
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail?.error?.message ?? body?.error?.message ?? res.statusText);
      }
      return (await res.json()) as NotificationConfigResponse;
    },
  });

  // Form local state — initialised from server response on first load.
  const cfg = configQuery.data ?? null;
  const [host, setHost] = React.useState("");
  const [port, setPort] = React.useState("587");
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [senderEmail, setSenderEmail] = React.useState("");
  const [senderName, setSenderName] = React.useState("AI API Manager");
  const [recipients, setRecipients] = React.useState("");
  const [enabled, setEnabled] = React.useState(true);
  const [hasInitialised, setHasInitialised] = React.useState(false);

  React.useEffect(() => {
    if (cfg && !hasInitialised) {
      setHost(cfg.smtp_host);
      setPort(String(cfg.smtp_port));
      setUsername(cfg.smtp_username);
      setSenderEmail(cfg.sender_email);
      setSenderName(cfg.sender_name);
      setRecipients(cfg.recipients.join(", "));
      setEnabled(cfg.enabled);
      setHasInitialised(true);
    }
  }, [cfg, hasInitialised]);

  const saveMut = useMutation<NotificationConfigResponse, ApiError>({
    mutationFn: async () => {
      const payload = {
        smtp_host: host.trim(),
        smtp_port: Number(port),
        smtp_username: username.trim(),
        smtp_password: password,
        sender_email: senderEmail.trim(),
        sender_name: senderName.trim() || "AI API Manager",
        recipients: recipients
          .split(/[,\s]+/)
          .map((r) => r.trim())
          .filter(Boolean),
        enabled,
      };
      return api<NotificationConfigResponse>("/admin/notifications/config", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: () => {
      toast({ title: "設定已儲存", description: "請使用「發測試信」確認連線可用" });
      setPassword("");
      queryClient.invalidateQueries({ queryKey: ["admin", "notifications", "config"] });
    },
    onError: (e) => toast({ title: "儲存失敗", description: e.message, variant: "destructive" }),
  });

  const deleteMut = useMutation<unknown, ApiError>({
    mutationFn: () => api("/admin/notifications/config", { method: "DELETE" }),
    onSuccess: () => {
      toast({ title: "通知設定已清除", description: "通知已停用" });
      setHost("");
      setPort("587");
      setUsername("");
      setPassword("");
      setSenderEmail("");
      setSenderName("AI API Manager");
      setRecipients("");
      setEnabled(true);
      setHasInitialised(false);
      queryClient.invalidateQueries({ queryKey: ["admin", "notifications", "config"] });
    },
    onError: (e) => toast({ title: "清除失敗", description: e.message, variant: "destructive" }),
  });

  const [testRecipient, setTestRecipient] = React.useState("");
  const testMut = useMutation<TestSendResponse, ApiError>({
    mutationFn: () =>
      api<TestSendResponse>("/admin/notifications/test-send", {
        method: "POST",
        body: JSON.stringify({ test_recipient: testRecipient.trim() }),
      }),
    onSuccess: (data) => {
      const isSuccess = data.outcome === "success";
      toast({
        title: isSuccess ? "✓ 測試信已寄出" : "✗ 測試失敗",
        description: data.message,
        variant: isSuccess ? "default" : "destructive",
      });
      queryClient.invalidateQueries({ queryKey: ["admin", "notifications", "config"] });
    },
    onError: (e) => toast({ title: "測試失敗", description: e.message, variant: "destructive" }),
  });

  const statusBadge = cfg ? STATUS_LABEL[cfg.status] : { text: "未設定", variant: "outline" as const };

  return (
    <div className="container mx-auto py-8 max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">管理員通知</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          設定 SMTP，平台會在分配被自動隔離、上游連續失敗、供應商憑證失效等重要事件
          發生時主動寄信通知。建議用 Gmail App Password 或學校既有 mail server。
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <div>
              <CardTitle className="text-lg">SMTP 設定</CardTitle>
              <CardDescription>
                密碼以 Fernet 加密儲存於資料庫；UI 僅顯示 fingerprint。
              </CardDescription>
            </div>
            <Badge variant={statusBadge.variant}>{statusBadge.text}</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label htmlFor="smtp-host">SMTP host</Label>
              <Input
                id="smtp-host"
                value={host}
                onChange={(e) => setHost(e.target.value)}
                placeholder="smtp.gmail.com"
              />
              <p className="text-xs text-muted-foreground">
                常見範例（點擊填入）：
                <button
                  type="button"
                  className="ml-1 font-mono text-primary hover:underline"
                  onClick={() => {
                    setHost("smtp.gmail.com");
                    setPort("587");
                  }}
                >
                  smtp.gmail.com
                </button>
              </p>
            </div>
            <div className="space-y-1">
              <Label htmlFor="smtp-port">SMTP port</Label>
              <Input
                id="smtp-port"
                type="number"
                value={port}
                onChange={(e) => setPort(e.target.value)}
                placeholder="587"
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="smtp-user">SMTP 帳號</Label>
            <Input
              id="smtp-user"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="ai-api-bot@school.edu.tw"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="smtp-pass">
              SMTP 密碼
              {cfg && (
                <span
                  className="ml-2 text-xs text-muted-foreground"
                  title="這是密碼的雜湊指紋，不是密碼本身。同一組密碼會得到相同指紋，可用來核對是否存對。"
                >
                  密碼指紋：<code>{cfg.smtp_password_fingerprint}</code>
                </span>
              )}
            </Label>
            {cfg && (
              <p className="text-xs text-muted-foreground">
                「密碼指紋」是密碼的雜湊（<strong>不是密碼本身</strong>），用來核對：同一組密碼永遠是同一個指紋。
              </p>
            )}
            <Input
              id="smtp-pass"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={cfg ? "（留白＝沿用已儲存的密碼）" : "貼上 Gmail App Password（空格會自動移除）"}
            />
            <p className="text-xs text-muted-foreground">
              Gmail 顯示的 App Password 有空格（如 <code>abcd efgh ijkl mnop</code>），可直接貼上，
              系統會自動移除空格。Gmail 需先開啟兩步驟驗證才能產生 App Password。
              搜尋關鍵字：<span className="font-mono">Gmail App Password 應用程式密碼 兩步驟驗證</span>
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label htmlFor="sender-email">寄件者 Email</Label>
              <Input
                id="sender-email"
                value={senderEmail}
                onChange={(e) => setSenderEmail(e.target.value)}
                placeholder="ai-api-bot@school.edu.tw"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="sender-name">寄件者顯示名稱</Label>
              <Input
                id="sender-name"
                value={senderName}
                onChange={(e) => setSenderName(e.target.value)}
                placeholder="AI API Manager"
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="recipients">收件人 Email（多個以逗號或空白分隔）</Label>
            <Input
              id="recipients"
              value={recipients}
              onChange={(e) => setRecipients(e.target.value)}
              placeholder="admin@school.edu.tw, ops@school.edu.tw"
            />
            <p className="text-xs text-muted-foreground">
              留白表示通知停用（會保留 SMTP 設定但不寄出）。
            </p>
          </div>

          <div className="flex items-center justify-between rounded-md border p-3">
            <div>
              <Label htmlFor="enabled" className="text-sm">啟用通知</Label>
              <p className="text-xs text-muted-foreground">關閉時所有事件略過，不會寄信。</p>
            </div>
            <Switch id="enabled" checked={enabled} onCheckedChange={setEnabled} />
          </div>

          <div className="flex items-center gap-2 pt-2">
            <Button onClick={() => saveMut.mutate()} disabled={saveMut.isPending}>
              {saveMut.isPending ? "儲存中…" : "儲存設定"}
            </Button>
            {cfg && (
              <Button
                variant="outline"
                onClick={() => {
                  if (confirm("確定要清除通知設定嗎？通知將停用。")) deleteMut.mutate();
                }}
                disabled={deleteMut.isPending}
              >
                清除設定
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">發測試信</CardTitle>
          <CardDescription>
            測試信會寄到您在下方輸入的「一次性收件人」，<strong>不會</strong>寄給上方的正式 recipients
            清單——避免設定階段誤打擾大家。
          </CardDescription>
          <CardDescription className="mt-1 text-xs">
            常見錯誤排查（可上網搜尋）：
            <span className="font-mono">「驗證失敗 535」→ Gmail App Password 錯</span>、
            <span className="font-mono">「連線失敗」→ host/port 或防火牆</span>、
            <span className="font-mono">「Gmail SMTP 設定 smtp.gmail.com 587」</span>。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="test-recipient">測試收件人 Email</Label>
            <Input
              id="test-recipient"
              type="email"
              value={testRecipient}
              onChange={(e) => setTestRecipient(e.target.value)}
              placeholder="your-own-email@school.edu.tw"
            />
          </div>
          <Button
            onClick={() => testMut.mutate()}
            disabled={testMut.isPending || !testRecipient.trim() || !cfg}
          >
            {testMut.isPending ? "寄送中…" : "發測試信"}
          </Button>
          {!cfg && (
            <p className="text-xs text-muted-foreground">請先儲存 SMTP 設定才能發測試信。</p>
          )}
          {testMut.data && (
            <div className="rounded-md border p-3 text-sm">
              <div className="font-medium">{testMut.data.outcome === "success" ? "✓ 成功" : "✗ 失敗"}</div>
              <div className="text-muted-foreground">{testMut.data.message}</div>
              {testMut.data.smtp_response_code !== null && (
                <div className="text-xs text-muted-foreground mt-1">
                  SMTP code: {testMut.data.smtp_response_code} · 耗時 {testMut.data.latency_ms} ms
                </div>
              )}
            </div>
          )}
          {cfg?.last_test_at && (
            <p className="text-xs text-muted-foreground">
              最近測試：{new Date(cfg.last_test_at).toLocaleString("zh-TW")} ·{" "}
              {cfg.last_test_outcome === "test_sent" ? "成功" : `失敗（${cfg.last_test_outcome ?? "unknown"}）`}
            </p>
          )}
        </CardContent>
      </Card>

      <NotificationHistory />
    </div>
  );
}

function NotificationHistory() {
  const historyQuery = useQuery<HistoryResponse, ApiError>({
    queryKey: ["admin", "notifications", "history"],
    queryFn: () => api<HistoryResponse>("/admin/notifications/history?limit=50"),
  });

  const rows = historyQuery.data?.rows ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">通知歷史</CardTitle>
        <CardDescription>最近的通知寄送紀錄（最新 50 筆）。被去重合併的事件會標示合併數。</CardDescription>
      </CardHeader>
      <CardContent>
        {historyQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">載入中…</p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">目前尚無通知紀錄。</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {rows.map((r) => {
              const isFailure = r.outcome.includes("failed");
              const failedRecipients = Object.entries(r.per_recipient_status).filter(
                ([, status]) => status !== "ok",
              );
              return (
                <li key={r.id} className="rounded-md border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Badge variant={isFailure ? "destructive" : "outline"}>
                        {outcomeLabel(r.outcome)}
                      </Badge>
                      <span className="font-mono text-xs text-muted-foreground">{r.event_type}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {new Date(r.created_at).toLocaleString("zh-TW")}
                    </span>
                  </div>
                  <div className="mt-1 text-muted-foreground">{r.subject}</div>
                  {r.bucket_event_count !== null && r.bucket_event_count > 1 && (
                    <div className="mt-1 text-xs text-amber-700">
                      共 {r.bucket_event_count} 筆同類事件合併入此封（5 分鐘去重）
                    </div>
                  )}
                  {isFailure && r.error_message && (
                    <div className="mt-1 text-xs text-destructive">
                      原因：{r.error_message}
                      {r.smtp_response_code ? `（SMTP ${r.smtp_response_code}）` : ""}
                    </div>
                  )}
                  {failedRecipients.length > 0 && (
                    <ul className="mt-1 text-xs text-destructive">
                      {failedRecipients.map(([addr, status]) => (
                        <li key={addr}>
                          {addr}：{status}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
