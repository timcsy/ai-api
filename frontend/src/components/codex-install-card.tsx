import * as React from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";
import { copyToClipboard } from "@/lib/clipboard";

type Os = "unix" | "windows";

function defaultOs(): Os {
  if (typeof navigator !== "undefined" && /win/i.test(navigator.userAgent)) return "windows";
  return "unix";
}

/**
 * Phase 19: dashboard "安裝 Codex" card. Shows a single copy-paste install
 * command per OS that points at this platform; the script runs a browser
 * device-flow (no token copy-paste). `baseUrl` is the canonical gateway URL.
 */
export function CodexInstallCard({ baseUrl }: { baseUrl: string }) {
  const { toast } = useToast();
  const [os, setOs] = React.useState<Os>(defaultOs);
  const base = baseUrl.replace(/\/$/, "");
  const command =
    os === "windows"
      ? `irm ${base}/install/codex.ps1 | iex`
      : `curl -fsSL ${base}/install/codex.sh | sh`;

  return (
    <Card className="mt-3">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">安裝 Codex（一行指令）</CardTitle>
        <CardDescription>
          複製到終端機執行，依指示在瀏覽器授權一次即可——不需貼 token、不需設環境變數。
          授權後會在你的「我的應用金鑰」新增一把金鑰給這台裝置。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="inline-flex rounded-md border text-xs">
          <button
            type="button"
            onClick={() => setOs("unix")}
            className={`px-2 py-1 rounded-l-md ${os === "unix" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
          >
            macOS / Linux
          </button>
          <button
            type="button"
            onClick={() => setOs("windows")}
            className={`px-2 py-1 rounded-r-md ${os === "windows" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
          >
            Windows
          </button>
        </div>
        <div className="flex items-stretch gap-2">
          <code className="block flex-1 min-w-0 break-all text-sm bg-muted px-2 py-1.5 rounded">
            {command}
          </code>
          <Button
            variant="outline"
            size="sm"
            onClick={async () => {
              await copyToClipboard(command);
              toast({ title: "已複製安裝指令" });
            }}
          >
            複製
          </Button>
        </div>
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer select-none">已經裝過 Codex？點此看會發生什麼</summary>
          <div className="mt-2 space-y-1.5 pl-1">
            <p>
              <strong>已裝 Codex 指令列（CLI）</strong>：不會重裝、也會保留你其他設定；只會把
              <strong>預設連線對象切到本平台</strong>，並用平台發的金鑰取代目前的登入。之後想換回自己的
              OpenAI 帳號，重新執行 <code className="break-all">codex login</code> 即可。
            </p>
            <p>
              <strong>已裝編輯器擴充（VS Code / Cursor 等的 Codex）</strong>：新版擴充與 CLI 共用同一份設定，
              通常會一起指向本平台。
            </p>
            <p>
              <strong>ChatGPT 桌面 App / 網頁版 Codex</strong>：那是綁 ChatGPT 帳號的版本，
              <strong>不適用</strong>本平台（請用上面的 CLI 安裝）。
            </p>
          </div>
        </details>
      </CardContent>
    </Card>
  );
}
