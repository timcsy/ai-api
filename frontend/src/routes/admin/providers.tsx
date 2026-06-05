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
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/use-toast";
import { ApiError, api } from "@/lib/api-client";
import { copyToClipboard } from "@/lib/clipboard";

interface ProviderCredential {
  id: string;
  provider: string;
  label: string;
  fingerprint: string;
  base_url: string | null;
  status: "active" | "disabled";
  last_used_at: string | null;
  created_at: string;
  created_by: string;
  disabled_at: string | null;
}

interface ProviderCredentialWithKey extends ProviderCredential {
  api_key?: string;
  warning?: {
    code: string;
    message: string;
    existing_label?: string;
  };
}

const PROVIDERS = ["azure", "openai", "anthropic", "gemini"] as const;

const createSchema = z.object({
  provider: z.enum(PROVIDERS),
  label: z.string().min(1).max(64),
  api_key: z.string().min(8, "key 至少 8 字元"),
  base_url: z.string().optional(),
  api_version: z.string().optional(),
});

const rotateSchema = z.object({
  api_key: z.string().min(8, "key 至少 8 字元"),
});

type CreateForm = z.infer<typeof createSchema>;
type RotateForm = z.infer<typeof rotateSchema>;

export function AdminProvidersPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [createOpen, setCreateOpen] = React.useState(false);
  const [rotateOpenFor, setRotateOpenFor] = React.useState<ProviderCredential | null>(null);
  const [disableConfirmFor, setDisableConfirmFor] = React.useState<ProviderCredential | null>(null);
  const [plaintextDialog, setPlaintextDialog] = React.useState<
    { title: string; api_key: string; fingerprint: string; warning?: string } | null
  >(null);
  const [showDisabled, setShowDisabled] = React.useState(false);

  const query = useQuery<ProviderCredential[], ApiError>({
    queryKey: ["admin", "providers"],
    queryFn: () => api<ProviderCredential[]>("/admin/providers"),
  });

  const visibleRows = React.useMemo(() => {
    if (!query.data) return [];
    return showDisabled ? query.data : query.data.filter((c) => c.status === "active");
  }, [query.data, showDisabled]);

  const createForm = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: { provider: "anthropic", label: "", api_key: "", base_url: "", api_version: "" },
  });
  const selectedProvider = createForm.watch("provider");
  const rotateForm = useForm<RotateForm>({
    resolver: zodResolver(rotateSchema),
    defaultValues: { api_key: "" },
  });

  const createMut = useMutation<ProviderCredentialWithKey, ApiError, CreateForm>({
    mutationFn: (data) =>
      api<ProviderCredentialWithKey>("/admin/providers", {
        method: "POST",
        body: JSON.stringify({
          provider: data.provider,
          label: data.label,
          api_key: data.api_key,
          base_url: data.base_url || null,
          extra_config: data.api_version ? { api_version: data.api_version } : null,
        }),
      }),
    onSuccess: (cred) => {
      setCreateOpen(false);
      createForm.reset();
      setPlaintextDialog({
        title: "Credential 已建立 — 一次性顯示明文",
        api_key: cred.api_key!,
        fingerprint: cred.fingerprint,
        warning: cred.warning
          ? `⚠ ${cred.warning.message}（既有：${cred.warning.existing_label ?? "?"}）`
          : undefined,
      });
      queryClient.invalidateQueries({ queryKey: ["admin", "providers"] });
    },
    onError: (e) => toast({ title: "建立失敗", description: e.message, variant: "destructive" }),
  });

  const rotateMut = useMutation<ProviderCredentialWithKey, ApiError, { id: string; data: RotateForm }>({
    mutationFn: ({ id, data }) =>
      api<ProviderCredentialWithKey>(`/admin/providers/${id}/rotate`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: (cred) => {
      setRotateOpenFor(null);
      rotateForm.reset();
      setPlaintextDialog({
        title: "新金鑰已生效 — 舊金鑰立即失效",
        api_key: cred.api_key!,
        fingerprint: cred.fingerprint,
      });
      queryClient.invalidateQueries({ queryKey: ["admin", "providers"] });
    },
    onError: (e) => toast({ title: "重新填寫失敗", description: e.message, variant: "destructive" }),
  });

  const disableMut = useMutation<ProviderCredential, ApiError, string>({
    mutationFn: (id) =>
      api<ProviderCredential>(`/admin/providers/${id}/disable`, { method: "POST" }),
    onSuccess: () => {
      setDisableConfirmFor(null);
      toast({ title: "已停用" });
      queryClient.invalidateQueries({ queryKey: ["admin", "providers"] });
    },
    onError: (e) => toast({ title: "停用失敗", description: e.message, variant: "destructive" }),
  });

  interface TestResult {
    ok: boolean;
    model: string;
    latency_ms?: number;
    error_type?: string;
    message?: string;
  }

  const testMut = useMutation<TestResult, ApiError, { id: string; model?: string }>({
    mutationFn: ({ id, model }) =>
      api<TestResult>(
        `/admin/providers/${id}/test-connection${model ? `?model=${encodeURIComponent(model)}` : ""}`,
        { method: "POST" },
      ),
    onSuccess: (r) => {
      if (r.ok) {
        toast({
          title: `✓ 連線成功（${r.latency_ms} ms）`,
          description: `model: ${r.model}`,
        });
      } else {
        toast({
          title: `✗ 連線失敗`,
          description: `${r.error_type}: ${r.message}`,
          variant: "destructive",
        });
      }
      queryClient.invalidateQueries({ queryKey: ["admin", "providers"] });
    },
    onError: (e) =>
      toast({ title: "測試失敗", description: e.message, variant: "destructive" }),
  });

  return (
    <div className="container mx-auto py-8 max-w-6xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">Provider 憑證</h1>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Switch
              id="show-disabled"
              checked={showDisabled}
              onCheckedChange={setShowDisabled}
            />
            <Label htmlFor="show-disabled" className="text-sm">含已停用</Label>
          </div>
          <Button onClick={() => setCreateOpen(true)}>新增</Button>
        </div>
      </div>

      <Table className="responsive-table">
        <TableHeader>
          <TableRow>
            <TableHead>供應商</TableHead>
            <TableHead>標記</TableHead>
            <TableHead>指紋</TableHead>
            <TableHead>狀態</TableHead>
            <TableHead>最後使用</TableHead>
            <TableHead>建立時間</TableHead>
            <TableHead className="text-right">動作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {query.isLoading && (
            <TableRow>
              <TableCell colSpan={7} className="text-muted-foreground">載入中…</TableCell>
            </TableRow>
          )}
          {visibleRows.length === 0 && !query.isLoading && (
            <TableRow>
              <TableCell colSpan={7} className="text-muted-foreground">
                {query.data && query.data.length > 0
                  ? "目前無 active credential；勾「含已停用」可看 disabled。"
                  : "尚未加入任何 provider 憑證；按「新增」開始。"}
              </TableCell>
            </TableRow>
          )}
          {visibleRows.map((c) => (
            <TableRow key={c.id}>
              <TableCell data-label="供應商">{c.provider}</TableCell>
              <TableCell data-label="標記">{c.label}</TableCell>
              <TableCell className="font-mono text-xs" data-label="指紋"><span className="block max-w-[140px] truncate">{c.fingerprint}</span></TableCell>
              <TableCell data-label="狀態">
                {c.status === "active" ? (
                  <Badge>active</Badge>
                ) : (
                  <Badge variant="secondary">disabled</Badge>
                )}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground" data-label="最後使用">
                {c.last_used_at ? new Date(c.last_used_at).toLocaleString() : "從未"}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground" data-label="建立時間">
                {new Date(c.created_at).toLocaleString()}
              </TableCell>
              <TableCell className="text-right" data-label="動作">
                {c.status === "active" && (
                  <div className="flex flex-wrap justify-end gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={testMut.isPending && testMut.variables?.id === c.id}
                      onClick={() => {
                        const customModel = window.prompt(
                          `測試 ${c.provider} credential（${c.label}）— 留空走預設 model；填入指定 model（Azure deployment 名稱 / OpenAI model id 等）`,
                          "",
                        );
                        if (customModel === null) return;
                        testMut.mutate({ id: c.id, model: customModel.trim() || undefined });
                      }}
                    >
                      {testMut.isPending && testMut.variables?.id === c.id ? "測試中…" : "測試連線"}
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setRotateOpenFor(c)}>
                      重新填寫金鑰
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setDisableConfirmFor(c)}>
                      停用
                    </Button>
                  </div>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新增 Provider 憑證</DialogTitle>
            <DialogDescription>
              明文 API key 僅在建立完成的下一個畫面顯示一次，離開後無法再取得。
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
                name="label"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Label</FormLabel>
                    <FormControl>
                      <Input placeholder="team-a-prod" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createForm.control}
                name="api_key"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>API Key（明文）</FormLabel>
                    <FormControl>
                      <Input type="password" placeholder="sk-..." {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createForm.control}
                name="base_url"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Base URL（{selectedProvider === "azure" ? "Azure 必填" : "選填"}）</FormLabel>
                    <FormControl>
                      <Input placeholder="https://your.openai.azure.com" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {selectedProvider === "azure" && (
                <FormField
                  control={createForm.control}
                  name="api_version"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>API Version（Azure，留空走 2024-06-01）</FormLabel>
                      <FormControl>
                        <Input placeholder="2025-04-01-preview" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
                  取消
                </Button>
                <Button type="submit" disabled={createMut.isPending}>
                  {createMut.isPending ? "建立中…" : "建立"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Rotate dialog */}
      <Dialog open={rotateOpenFor !== null} onOpenChange={(v) => !v && setRotateOpenFor(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>重新填寫上游金鑰</DialogTitle>
            <DialogDescription>
              貼上新 API key。舊 key 立即失效；新 key 僅在下一個畫面顯示一次。
            </DialogDescription>
          </DialogHeader>
          <Form {...rotateForm}>
            <form
              onSubmit={rotateForm.handleSubmit((d) => {
                if (rotateOpenFor) rotateMut.mutate({ id: rotateOpenFor.id, data: d });
              })}
              className="space-y-4"
            >
              <FormField
                control={rotateForm.control}
                name="api_key"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>新 API Key</FormLabel>
                    <FormControl>
                      <Input type="password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setRotateOpenFor(null)}>
                  取消
                </Button>
                <Button type="submit" disabled={rotateMut.isPending}>
                  重新填寫
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Disable confirm */}
      <AlertDialog
        open={disableConfirmFor !== null}
        onOpenChange={(v) => !v && setDisableConfirmFor(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>停用此 credential？</AlertDialogTitle>
            <AlertDialogDescription>
              停用後，依賴此 credential 的所有 model 對成員立即不可用。
              {disableConfirmFor && (
                <span className="block mt-2 font-mono text-xs">
                  {disableConfirmFor.provider} / {disableConfirmFor.label}
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => disableConfirmFor && disableMut.mutate(disableConfirmFor.id)}
            >
              停用
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* One-time plaintext display */}
      <Dialog open={plaintextDialog !== null} onOpenChange={(v) => !v && setPlaintextDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{plaintextDialog?.title}</DialogTitle>
            <DialogDescription>
              這是<strong>唯一一次</strong>可以看到明文的機會。請立即複製到安全的地方。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            {plaintextDialog?.warning && (
              <div className="rounded-md border border-amber-500 bg-amber-50 p-2 text-xs text-amber-900">
                {plaintextDialog.warning}
              </div>
            )}
            <div>
              <div className="text-xs text-muted-foreground mb-1">Fingerprint</div>
              <code className="text-xs">{plaintextDialog?.fingerprint}</code>
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">API Key（明文）</div>
              <pre className="bg-muted rounded-md p-3 text-xs break-all whitespace-pre-wrap">
                {plaintextDialog?.api_key}
              </pre>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={async () => {
                if (plaintextDialog) {
                  const ok = await copyToClipboard(plaintextDialog.api_key);
                  toast({ title: ok ? "已複製" : "複製失敗" });
                }
              }}
            >
              複製
            </Button>
          </div>
          <DialogFooter>
            <Button onClick={() => setPlaintextDialog(null)}>我已保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
