import type { ComponentType } from "react";

import { CodexAppDetail } from "@/components/codex-app-detail";
import { CodexLogo } from "@/components/app-logos";

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
];

export function getApplication(id: string | undefined): Application | undefined {
  return APPLICATIONS.find((a) => a.id === id);
}
