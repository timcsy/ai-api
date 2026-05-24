import { act, renderHook } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";

import {
  buildCatalogQueryKey,
  buildCatalogQueryString,
  useCatalogFilters,
} from "@/hooks/use-catalog-filters";

function makeWrapper(initialEntries: string[]) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>;
  };
}

describe("useCatalogFilters()", () => {
  it("parses an empty URL to default-empty filters", () => {
    const { result } = renderHook(() => useCatalogFilters(), {
      wrapper: makeWrapper(["/catalog"]),
    });
    expect(result.current.filters).toEqual({
      capability: [],
      modality_input: [],
      modality_output: [],
      recommended_for: [],
      cost_tier: null,
      include_deprecated: false,
    });
  });

  it("parses a URL with multiple capabilities (AND list)", () => {
    const { result } = renderHook(() => useCatalogFilters(), {
      wrapper: makeWrapper(["/catalog?capability=vision&capability=function-calling&cost_tier=low"]),
    });
    expect(result.current.filters.capability).toEqual(["vision", "function-calling"]);
    expect(result.current.filters.cost_tier).toBe("low");
  });

  it("toggleList adds then removes a list value (and updates URL)", () => {
    function Probe() {
      const hook = useCatalogFilters();
      const loc = useLocation();
      return { hook, search: loc.search };
    }
    const { result } = renderHook(() => Probe(), {
      wrapper: makeWrapper(["/catalog"]),
    });

    act(() => result.current.hook.toggleList("capability", "vision"));
    expect(result.current.hook.filters.capability).toEqual(["vision"]);
    expect(result.current.search).toContain("capability=vision");

    act(() => result.current.hook.toggleList("capability", "vision"));
    expect(result.current.hook.filters.capability).toEqual([]);
    expect(result.current.search).not.toContain("capability=vision");
  });

  it("setCostTier sets and clears", () => {
    const { result } = renderHook(() => useCatalogFilters(), {
      wrapper: makeWrapper(["/catalog"]),
    });
    act(() => result.current.setCostTier("low"));
    expect(result.current.filters.cost_tier).toBe("low");
    act(() => result.current.setCostTier(null));
    expect(result.current.filters.cost_tier).toBeNull();
  });

  it("setIncludeDeprecated toggles", () => {
    const { result } = renderHook(() => useCatalogFilters(), {
      wrapper: makeWrapper(["/catalog"]),
    });
    act(() => result.current.setIncludeDeprecated(true));
    expect(result.current.filters.include_deprecated).toBe(true);
    act(() => result.current.setIncludeDeprecated(false));
    expect(result.current.filters.include_deprecated).toBe(false);
  });

  it("clear empties all filters", () => {
    const { result } = renderHook(() => useCatalogFilters(), {
      wrapper: makeWrapper(["/catalog?capability=vision&cost_tier=low"]),
    });
    act(() => result.current.clear());
    expect(result.current.filters.capability).toEqual([]);
    expect(result.current.filters.cost_tier).toBeNull();
  });

  it("buildCatalogQueryKey is stable across input order", () => {
    const k1 = buildCatalogQueryKey({
      capability: ["vision", "function-calling"],
      modality_input: [],
      modality_output: [],
      recommended_for: [],
      cost_tier: "low",
      include_deprecated: false,
    });
    const k2 = buildCatalogQueryKey({
      capability: ["function-calling", "vision"],
      modality_input: [],
      modality_output: [],
      recommended_for: [],
      cost_tier: "low",
      include_deprecated: false,
    });
    expect(JSON.stringify(k1)).toBe(JSON.stringify(k2));
  });

  it("buildCatalogQueryString produces a backend-compatible query", () => {
    const qs = buildCatalogQueryString({
      capability: ["vision", "function-calling"],
      modality_input: [],
      modality_output: [],
      recommended_for: [],
      cost_tier: "low",
      include_deprecated: false,
    });
    expect(qs).toContain("capability=vision");
    expect(qs).toContain("capability=function-calling");
    expect(qs).toContain("cost_tier=low");
  });
});
