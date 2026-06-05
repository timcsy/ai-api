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
      </CardContent>
    </Card>
  );
}
