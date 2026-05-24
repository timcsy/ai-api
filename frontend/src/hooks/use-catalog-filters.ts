import * as React from "react";
import { useSearchParams } from "react-router-dom";

export type ListFilter = "capability" | "modality_input" | "modality_output" | "recommended_for";

export interface CatalogFilters {
  capability: string[];
  modality_input: string[];
  modality_output: string[];
  recommended_for: string[];
  cost_tier: string | null;
  include_deprecated: boolean;
}

export interface UseCatalogFiltersResult {
  filters: CatalogFilters;
  toggleList: (key: ListFilter, value: string) => void;
  setCostTier: (value: string | null) => void;
  setIncludeDeprecated: (value: boolean) => void;
  clear: () => void;
}

export function useCatalogFilters(): UseCatalogFiltersResult {
  const [params, setParams] = useSearchParams();

  const filters: CatalogFilters = React.useMemo(
    () => ({
      capability: params.getAll("capability"),
      modality_input: params.getAll("modality_input"),
      modality_output: params.getAll("modality_output"),
      recommended_for: params.getAll("recommended_for"),
      cost_tier: params.get("cost_tier"),
      include_deprecated: params.get("include_deprecated") === "true",
    }),
    [params],
  );

  const toggleList = React.useCallback(
    (key: ListFilter, value: string) => {
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        const existing = next.getAll(key);
        if (existing.includes(value)) {
          next.delete(key);
          existing.filter((v) => v !== value).forEach((v) => next.append(key, v));
        } else {
          next.append(key, value);
        }
        return next;
      });
    },
    [setParams],
  );

  const setCostTier = React.useCallback(
    (value: string | null) => {
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value === null) next.delete("cost_tier");
        else next.set("cost_tier", value);
        return next;
      });
    },
    [setParams],
  );

  const setIncludeDeprecated = React.useCallback(
    (value: boolean) => {
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value) next.set("include_deprecated", "true");
        else next.delete("include_deprecated");
        return next;
      });
    },
    [setParams],
  );

  const clear = React.useCallback(() => {
    setParams(new URLSearchParams());
  }, [setParams]);

  return { filters, toggleList, setCostTier, setIncludeDeprecated, clear };
}

/** Build TanStack Query key from current filters. */
export function buildCatalogQueryKey(filters: CatalogFilters): readonly unknown[] {
  return [
    "catalog",
    "models",
    {
      capability: [...filters.capability].sort(),
      modality_input: [...filters.modality_input].sort(),
      modality_output: [...filters.modality_output].sort(),
      recommended_for: [...filters.recommended_for].sort(),
      cost_tier: filters.cost_tier,
      include_deprecated: filters.include_deprecated,
    },
  ];
}

/** Build URL query string for /catalog/models from filters. */
export function buildCatalogQueryString(filters: CatalogFilters): string {
  const sp = new URLSearchParams();
  for (const v of filters.capability) sp.append("capability", v);
  for (const v of filters.modality_input) sp.append("modality_input", v);
  for (const v of filters.modality_output) sp.append("modality_output", v);
  for (const v of filters.recommended_for) sp.append("recommended_for", v);
  if (filters.cost_tier) sp.set("cost_tier", filters.cost_tier);
  if (filters.include_deprecated) sp.set("include_deprecated", "true");
  const s = sp.toString();
  return s ? `?${s}` : "";
}
