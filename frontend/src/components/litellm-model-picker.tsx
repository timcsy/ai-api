import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api-client";

export interface LitellmSuggestPrice {
  input_per_1k: string;
  output_per_1k: string;
  cached_input_per_1k: string | null;
}
export interface LitellmDraft {
  key: string;
  slug_default: string;
  metadata: {
    context_window: number;
    modality_input: string[];
    modality_output: string[];
    capabilities: string[];
  };
  suggested_price: LitellmSuggestPrice | null;
  imported_version: string;
}
interface SearchHit {
  key: string;
  provider: string | null;
  mode: string | null;
  context_window: number;
  supports_vision: boolean;
  suggested_price: LitellmSuggestPrice | null;
}

/**
 * Phase 23: search LiteLLM's built-in registry and bring a model's metadata +
 * suggested price into the create form (kills cold-start hand-entry).
 */
export function LiteLLMModelPicker({ onPick }: { onPick: (draft: LitellmDraft) => void }) {
  const [q, setQ] = React.useState("");
  const [hits, setHits] = React.useState<SearchHit[]>([]);
  const [searching, setSearching] = React.useState(false);

  async function runSearch() {
    if (!q.trim()) return;
    setSearching(true);
    try {
      const r = await api<{ results: SearchHit[] }>(
        `/admin/catalog/litellm/search?q=${encodeURIComponent(q.trim())}&limit=15`,
      );
      setHits(r.results);
    } finally {
      setSearching(false);
    }
  }

  async function pick(key: string) {
    const draft = await api<LitellmDraft>(
      `/admin/catalog/litellm/suggest/${key}`,
    );
    onPick(draft);
    setHits([]);
    setQ("");
  }

  return (
    <div className="rounded-md border bg-muted/30 p-3 space-y-2">
      <div className="text-sm font-medium">從 LiteLLM 帶入（免手打 context / 能力 / 建議價）</div>
      <div className="flex gap-2">
        <Input
          value={q}
          placeholder="搜尋模型，例如 gpt-4o / claude / gemini"
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void runSearch();
            }
          }}
        />
        <Button type="button" variant="outline" size="sm" onClick={() => void runSearch()} disabled={searching}>
          {searching ? "搜尋中…" : "搜尋"}
        </Button>
      </div>
      {hits.length > 0 && (
        <ul className="max-h-48 space-y-1 overflow-y-auto">
          {hits.map((h) => (
            <li key={h.key}>
              <button
                type="button"
                onClick={() => void pick(h.key)}
                className="flex w-full items-center justify-between gap-2 rounded px-2 py-1 text-left text-xs hover:bg-accent"
              >
                <span className="font-mono">{h.key}</span>
                <span className="shrink-0 text-muted-foreground">
                  {h.context_window.toLocaleString()} ctx
                  {h.suggested_price ? ` · $${h.suggested_price.input_per_1k}/1k` : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
