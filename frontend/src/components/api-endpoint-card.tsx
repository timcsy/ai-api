import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/contexts/auth";
import { apiBaseUrl } from "@/lib/api-base";

/**
 * Phase 22: extracted from the old single-scroll dashboard. Shows the gateway
 * base URL + the one-time-token hint. Lives on the 金鑰 page now.
 */
export function ApiEndpointCard() {
  const { member } = useAuth();
  return (
    <>
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">API 端點</CardTitle>
          <CardDescription>
            呼叫時將 token 放於 <code className="text-xs">Authorization: Bearer</code> 標頭
          </CardDescription>
        </CardHeader>
        <CardContent>
          <code className="block break-all text-sm bg-muted px-2 py-1 rounded">
            {apiBaseUrl()}
          </code>
          {member?.gateway_base_url &&
            !window.location.origin.startsWith(member.gateway_base_url) && (
            <p className="text-xs text-muted-foreground mt-2">
              如果你從其他主機呼叫，可改用 admin 設定的 base URL：
              <code className="ml-1 break-all">{member.gateway_base_url}/v1</code>
            </p>
          )}
        </CardContent>
      </Card>
      <Alert className="mt-3">
        <AlertDescription>
          API token 在你<strong>自助領取</strong>或管理員建立分配時一次性顯示；系統僅保存雜湊。
          如需取得新 token，請進入單筆分配後點「重新產生 token」（舊 token 立即失效）。
        </AlertDescription>
      </Alert>
    </>
  );
}
