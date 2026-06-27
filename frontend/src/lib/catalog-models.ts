import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

/** Phase 34 (049): member catalog model meta needed to pick the right usage example.
 * Single source of "slug → {kind, display_name, supportsResponses}" so the keys page
 * and the apps "Direct API" card can join their model lists with the right example. */
interface CatalogModelRaw {
  slug: string;
  display_name: string;
  kind?: string;
  responses_support?: { state?: string } | null;
}

export interface ModelMeta {
  slug: string;
  displayName: string;
  kind?: string;
  supportsResponses: boolean;
}

function toMeta(m: CatalogModelRaw): ModelMeta {
  return {
    slug: m.slug,
    displayName: m.display_name,
    kind: m.kind,
    supportsResponses: m.responses_support?.state === "available",
  };
}

/** Fetch the member-visible catalog and expose a slug→meta lookup. Reuses the same
 * endpoint the catalog page uses (cached by TanStack Query). */
export function useCatalogModels() {
  const q = useQuery<CatalogModelRaw[]>({
    queryKey: ["catalog", "models", "all"],
    queryFn: () => api<CatalogModelRaw[]>("/catalog/models"),
  });
  const bySlug = new Map<string, ModelMeta>();
  for (const m of q.data ?? []) bySlug.set(m.slug, toMeta(m));
  return {
    bySlug,
    models: [...bySlug.values()],
    isLoading: q.isLoading,
    isSuccess: q.isSuccess,
  };
}
