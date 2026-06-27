import * as React from "react";

import { ApiUsageExample } from "@/components/api-usage-example";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/** Phase 34 (049): "how to call" explorer — pick a model, see the right example.
 * Shared by the keys page ("如何使用這把金鑰") and the apps "Direct API / SDK" card,
 * so the example lives in exactly ONE place (ApiUsageExample) and never drifts. */
export interface ExplorerModel {
  slug: string;
  label: string;
  kind?: string;
  supportsResponses: boolean;
}

export function UsageExplorer({
  models,
  emptyHint,
}: {
  models: ExplorerModel[];
  emptyHint: React.ReactNode;
}) {
  const [selected, setSelected] = React.useState<string | undefined>(models[0]?.slug);

  // Keep selection valid as the model list loads/changes.
  React.useEffect(() => {
    const first = models[0];
    if (first && !models.some((m) => m.slug === selected)) {
      setSelected(first.slug);
    }
  }, [models, selected]);

  const current = models.find((m) => m.slug === selected) ?? models[0];
  if (!current) {
    return <p className="text-muted-foreground text-sm">{emptyHint}</p>;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground shrink-0">選一個模型：</span>
        <Select value={current.slug} onValueChange={setSelected}>
          <SelectTrigger className="w-full max-w-xs" aria-label="選擇模型">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {models.map((m) => (
              <SelectItem key={m.slug} value={m.slug}>
                {m.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <ApiUsageExample
        model={current.slug}
        kind={current.kind}
        supportsResponses={current.supportsResponses}
        isEmbedding={current.kind === "embedding"}
        isOcr={current.kind === "ocr"}
      />
    </div>
  );
}
