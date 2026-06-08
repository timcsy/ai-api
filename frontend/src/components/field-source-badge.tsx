import { Badge } from "@/components/ui/badge";

export type FieldSource = "litellm" | "borrowed" | "manual";

const LABEL: Record<FieldSource, string> = {
  litellm: "LiteLLM",
  borrowed: "借用",
  manual: "手動",
};

/**
 * Phase 24: shows where a catalog field's value came from (from litellm_sync.
 * field_sources), so admins see at a glance which values are auto-brought-in
 * vs hand-edited. Renders nothing for models with no LiteLLM provenance.
 */
export function FieldSourceBadge({ source }: { source: FieldSource | undefined }) {
  if (!source) return null;
  return (
    <Badge
      variant={source === "manual" ? "outline" : "secondary"}
      className="ml-1.5 align-middle text-[10px] font-normal"
    >
      {LABEL[source]}
    </Badge>
  );
}
