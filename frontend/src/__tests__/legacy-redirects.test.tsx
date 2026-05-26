import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { LegacyRedirectRoutes } from "@/lib/legacy-redirects";

function LocationProbe() {
  const loc = useLocation();
  return <div data-testid="path">{loc.pathname + loc.search}</div>;
}

const cases: Array<[string, string]> = [
  ["/admin/catalog-manage", "/admin/model"],
  ["/admin/model-access", "/admin/model"],
  ["/admin/catalog", "/admin/model"],
  ["/admin/allocations", "/admin/observability/allocations"],
  ["/admin/tags", "/admin/tag"],
  ["/admin/usage", "/admin/observability/usage"],
  ["/admin/quota-pool", "/admin/observability/quota"],
  ["/admin/rebalance-log", "/admin/observability/rebalance"],
  ["/admin/audit", "/admin/observability/audit"],
];

describe("LegacyRedirectRoutes", () => {
  for (const [from, to] of cases) {
    it(`redirects ${from} → ${to}`, () => {
      render(
        <MemoryRouter initialEntries={[from]}>
          <Routes>
            {LegacyRedirectRoutes()}
            <Route path="*" element={<LocationProbe />} />
          </Routes>
        </MemoryRouter>,
      );
      expect(screen.getByTestId("path").textContent).toBe(to);
    });
  }
});
