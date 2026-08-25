import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { ApiError, api } from "@/lib/api-client";

interface OAuthConfig {
  redirect_allowlist: string;
  prefixes: string[];
  updated_at: string | null;
  updated_by: string | null;
}

/**
 * Admin page for the OAuth redirect_uri allowlist — the anti-open-redirect
 * defense for the first-party Authorization Code flow. Empty = fail-closed
 * (OAuth is refused). One prefix per line.
 */
export function AdminOAuthPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [text, setText] = React.useState<string | null>(null);

  const query = useQuery<OAuthConfig, ApiError>({
    queryKey: ["admin", "oauth-config"],
    queryFn: () => api<OAuthConfig>("/admin/oauth/config"),
  });

  // Seed the editor once from the server (prefixes → one per line).
  React.useEffect(() => {
    if (query.data && text === null) setText(query.data.prefixes.join("\n"));
  }, [query.data, text]);

  const saveMut = useMutation<OAuthConfig, ApiError, string>({
    mutationFn: (value) =>
      api<OAuthConfig>("/admin/oauth/config", {
        method: "PUT",
        // Store newline-separated; the backend accepts comma or newline.
        body: JSON.stringify({ redirect_allowlist: value }),
      }),
    onSuccess: (cfg) => {
      queryClient.setQueryData(["admin", "oauth-config"], cfg);
      setText(cfg.prefixes.join("\n"));
      toast({ title: "已儲存", description: `目前允許 ${cfg.prefixes.length} 個返回網址前綴` });
    },
    onError: (e) => toast({ title: "儲存失敗", description: e.message, variant: "destructive" }),
  });

  return (
    <div className="container mx-auto max-w-2xl py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">應用授權（OAuth）</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          第一方網頁應用透過 OAuth 導轉領取金鑰時,只允許把授權碼送回「允許清單」內的返回網址（redirect_uri）。
          這是防止授權碼被劫持的關鍵設定。
        </p>
      </div>

      {query.isLoading && <p className="text-muted-foreground">載入中…</p>}
      {query.error && (
        <Alert variant="destructive">
          <AlertDescription>無法載入：{query.error.message}</AlertDescription>
        </Alert>
      )}

      {text !== null && (
        <div className="space-y-3">
          <label className="text-sm font-medium">允許的返回網址前綴（一行一個）</label>
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={8}
            placeholder={"https://myapp.ccsh.tn.edu.tw/\nhttps://other.app/callback"}
            className="font-mono text-sm"
          />
          <Alert>
            <AlertDescription className="text-xs">
              以<strong>前綴比對</strong>：返回網址只要以清單中任一項開頭即通過。
              <strong>留空 = 一律拒絕（關閉 OAuth）</strong>。建議填到能明確辨識你的應用網域,別用過寬的前綴。
            </AlertDescription>
          </Alert>
          <div className="flex items-center gap-3">
            <Button
              disabled={saveMut.isPending || text === (query.data?.prefixes.join("\n") ?? "")}
              onClick={() => saveMut.mutate(text)}
            >
              {saveMut.isPending ? "儲存中…" : "儲存"}
            </Button>
            {query.data?.updated_at && (
              <span className="text-xs text-muted-foreground">
                上次更新：{new Date(query.data.updated_at).toLocaleString("zh-TW")}
                {query.data.updated_by ? `（${query.data.updated_by}）` : ""}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
