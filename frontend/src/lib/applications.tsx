import type { ComponentType } from "react";

import { CodexAppDetail } from "@/components/codex-app-detail";
import { ApiLogo, CodexLogo, CopilotLogo } from "@/components/app-logos";
import { CopilotAppDetail } from "@/components/copilot-app-detail";
import { DirectApiDetail } from "@/components/direct-api-detail";

export interface Application {
  id: string;
  name: string;
  blurb: string;
  Logo: ComponentType<{ className?: string }>;
  Detail: ComponentType;
}

/** Phase 28: storefront registry. v1 ships Codex only — more OpenAI-compatible
 * apps slot in as entries (each adds a tile + a detail page automatically). */
export const APPLICATIONS: Application[] = [
  {
    id: "codex",
    name: "Codex",
    blurb: "OpenAI 的 agent 工具——CLI / IDE 擴充 / 桌面 App 都能接上本平台。",
    Logo: CodexLogo,
    Detail: CodexAppDetail,
  },
  {
    id: "copilot",
    name: "GitHub Copilot",
    blurb: "VS Code 的 AI 助理——指向本平台的 OpenAI 相容端點，用你的金鑰即可。",
    Logo: CopilotLogo,
    Detail: CopilotAppDetail,
  },
  {
    id: "api",
    name: "直接用 API / SDK",
    blurb: "自己寫程式？OpenAI 相容端點 + 你的金鑰，curl / Python / JS 範例一鍵複製。",
    Logo: ApiLogo,
    Detail: DirectApiDetail,
  },
];

export function getApplication(id: string | undefined): Application | undefined {
  return APPLICATIONS.find((a) => a.id === id);
}
