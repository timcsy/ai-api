import * as React from "react";
import { useSearchParams } from "react-router-dom";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { ApiError, api } from "@/lib/api-client";

interface ConsentInfo {
  id: string;
  client_name: string;
  redirect_uri: string;
  scope: string | null;
  allocations: { id: string; resource_model: string; display_name: string | null }[];
}

/**
 * OAuth Authorization Code + PKCE consent page (`/oauth/authorize`). A first-party
 * web app redirects the (logged-in) member here with the standard params; they
 * pick which allocations to grant and approve, which mints a one-time code we send
 * back to the app's redirect_uri. The app then exchanges it at /oauth/token.
 */
export function OAuthAuthorizePage() {
  const [params] = useSearchParams();
  const { toast } = useToast();
  const started = React.useRef(false);
  const [info, setInfo] = React.useState<ConsentInfo | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [pick, setPick] = React.useState<Set<string>>(new Set());
  const [busy, setBusy] = React.useState(false);

  const clientName = params.get("client_name") ?? "";
  const redirectUri = params.get("redirect_uri") ?? "";
  const codeChallenge = params.get("code_challenge") ?? "";
  const codeChallengeMethod = params.get("code_challenge_method") ?? "S256";
  const state = params.get("state");
  const scope = params.get("scope");

  // Register the consent once (creates a pending authorization + returns the
  // member's allocations to grant). Guarded against React strict-mode double-run.
  React.useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (!redirectUri || !codeChallenge || !clientName) {
      setError("缺少必要參數（client_name / redirect_uri / code_challenge）。");
      return;
    }
    api<ConsentInfo>("/me/oauth/consent", {
      method: "POST",
      body: JSON.stringify({
        client_name: clientName,
        redirect_uri: redirectUri,
        code_challenge: codeChallenge,
        code_challenge_method: codeChallengeMethod,
        state,
        scope,
      }),
    })
      .then(setInfo)
      .catch((e: ApiError) =>
        setError(
          e.code === "redirect_uri_not_allowed"
            ? "此應用的返回網址不在允許清單中，無法授權（請聯絡管理員）。"
            : e.message,
        ),
      );
  }, [clientName, redirectUri, codeChallenge, codeChallengeMethod, state, scope]);

  const redirectBack = (extra: Record<string, string | null | undefined>) => {
    const u = new URL(info!.redirect_uri);
    for (const [k, v] of Object.entries(extra)) if (v != null) u.searchParams.set(k, v);
    window.location.href = u.toString();
  };

  const approve = async () => {
    if (!info) return;
    setBusy(true);
    try {
      const r = await api<{ redirect_uri: string; code: string; state: string | null }>(
        `/me/oauth/${info.id}/approve`,
        { method: "POST", body: JSON.stringify({ allocation_ids: [...pick] }) },
      );
      redirectBack({ code: r.code, state: r.state });
    } catch (e) {
      setBusy(false);
      toast({ title: "授權失敗", description: (e as ApiError).message, variant: "destructive" });
    }
  };

  const deny = async () => {
    if (!info) return;
    setBusy(true);
    try {
      const r = await api<{ redirect_uri: string; error: string; state: string | null }>(
        `/me/oauth/${info.id}/deny`,
        { method: "POST" },
      );
      redirectBack({ error: r.error, state: r.state });
    } catch (e) {
      setBusy(false);
      toast({ title: "操作失敗", description: (e as ApiError).message, variant: "destructive" });
    }
  };

  return (
    <div className="container mx-auto max-w-md py-10">
      <Card>
        <CardHeader>
          <CardTitle>授權應用程式</CardTitle>
          <CardDescription>
            {info ? (
              <>
                <span className="font-medium text-foreground">「{info.client_name}」</span>
                想以你的身分使用 AI API。核准後會在你的「應用金鑰」新增一把金鑰給它,可隨時撤回。
              </>
            ) : (
              "確認要授權的應用與範圍。"
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {info && (
            <>
              <div className="text-xs text-muted-foreground break-all">
                返回網址：{info.redirect_uri}
              </div>
              <div className="space-y-2">
                <Label>要授權哪些模型配額（可多選）</Label>
                <div className="max-h-48 space-y-1 overflow-y-auto rounded-md border p-2">
                  {info.allocations.map((a) => (
                    <label key={a.id} className="flex items-center gap-2 py-1 text-sm">
                      <Checkbox
                        checked={pick.has(a.id)}
                        onCheckedChange={(v) =>
                          setPick((s) => {
                            const n = new Set(s);
                            if (v) n.add(a.id);
                            else n.delete(a.id);
                            return n;
                          })
                        }
                      />
                      <span className="font-mono text-xs">{a.display_name ?? a.resource_model}</span>
                    </label>
                  ))}
                </div>
                {info.allocations.length === 0 && (
                  <p className="text-xs text-muted-foreground">
                    你還沒有可用的分配,請先到儀表板領取一個模型。
                  </p>
                )}
              </div>
              <div className="flex gap-2">
                <Button className="flex-1" disabled={pick.size === 0 || busy} onClick={() => void approve()}>
                  {busy ? "處理中…" : "核准"}
                </Button>
                <Button variant="outline" disabled={busy} onClick={() => void deny()}>
                  拒絕
                </Button>
              </div>
            </>
          )}

          {!info && !error && <p className="text-sm text-muted-foreground">載入中…</p>}
        </CardContent>
      </Card>
    </div>
  );
}
