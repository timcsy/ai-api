const show = (v: unknown): string =>
  v === null || v === undefined
    ? "—"
    : Array.isArray(v)
      ? v.join(", ")
      : typeof v === "object"
        ? JSON.stringify(v)
        : String(v);

/**
 * Phase 24: read-only "LiteLLM 原始資訊" panel. Shows the full registry entry we
 * stored in litellm_sync.raw (mode, max_output_tokens, all capability/price
 * fields) without polluting the editable catalog fields. Renders nothing when
 * the model has no LiteLLM counterpart.
 */
export function LiteLLMRawPanel({ raw }: { raw: Record<string, unknown> | null | undefined }) {
  if (!raw || Object.keys(raw).length === 0) return null;
  const entries = Object.entries(raw).sort(([a], [b]) => a.localeCompare(b));
  return (
    <details className="rounded-md border bg-muted/30 p-3 text-sm">
      <summary className="cursor-pointer select-none font-medium">LiteLLM 原始資訊（唯讀）</summary>
      <dl className="mt-2 grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2">
        {entries.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-2 border-b border-border/40 py-0.5">
            <dt className="font-mono text-xs text-muted-foreground">{k}</dt>
            <dd className="text-right font-mono text-xs break-all">{show(v)}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
