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
          <div className="mt-2 space-y-2 pl-1">
            <p>
              這個安裝寫進 <code className="break-all">~/.codex</code> 設定 + 一把平台金鑰。讀這份設定的 Codex
              介面都能指向本平台；跑在雲端、綁 ChatGPT 帳號的則不行。
            </p>
            <div>
              <p className="font-medium text-foreground">✓ 適用</p>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                <li>
                  <strong>指令列（CLI）</strong>（最穩、推薦）：不會重裝、保留你其他設定；只把<strong>預設連線對象切到本平台</strong>、
                  用平台金鑰取代目前登入。想換回自己的 OpenAI 帳號，重跑 <code className="break-all">codex login</code> 即可（可逆）。
                </li>
                <li>
                  <strong>編輯器擴充（VS Code / Cursor / JetBrains 的 Codex）</strong>：與 CLI 共用同一份設定，
                  從各自的 marketplace 裝好後通常會一起指向本平台、<strong>免再設定</strong>。
                </li>
                <li>
                  <strong>Codex 桌面 App</strong>：用上面的一鍵安裝（走 CLI 寫好共用設定）後，桌面 App 開起來讀同一份
                  <code className="break-all"> ~/.codex</code> 就能用、<strong>免再設定</strong>。
                  （別在 App 自己的 GUI 手動填 API key——那條目前有已知問題；走共用設定這條最穩。）
                </li>
              </ul>
            </div>
            <div>
              <p className="font-medium text-foreground">✗ 不適用</p>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                <li>
                  <strong>網頁版 Codex（chatgpt.com/codex）</strong>：跑在 OpenAI 雲端、綁 ChatGPT 帳號，不經本地設定 → 請用 <strong>CLI</strong>。
                </li>
              </ul>
            </div>
          </div>
        </details>
        <p className="text-xs text-muted-foreground">
          想了解 Codex 怎麼用（指令、功能）？見{" "}
          <a
            href="https://developers.openai.com/codex"
            target="_blank"
            rel="noreferrer"
            className="underline underline-offset-2 hover:text-foreground"
          >
            Codex 官方說明
          </a>
          。（登入／連線本平台請用上面的一行指令，不要在官方頁面用 ChatGPT 帳號重新登入。）
        </p>
      </CardContent>
    </Card>
  );
}
