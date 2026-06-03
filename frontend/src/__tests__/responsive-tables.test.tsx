import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { AdminMembersPage } from "@/routes/admin/members";
import { AdminUsagePage } from "@/routes/admin/usage";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderWithProviders(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        {ui}
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/**
 * Phase 16 (US3) contract: every wide table marked `.responsive-table` must give
 * each body cell a non-empty `data-label`, so the mobile card-stack shows the
 * field name beside each value (see contracts/ui-contracts.md, contract 1).
 */
function expectResponsiveTableContract(container: HTMLElement) {
  const table = container.querySelector("table.responsive-table");
  expect(table).not.toBeNull();
  const bodyCells = table!.querySelectorAll("tbody td");
  expect(bodyCells.length).toBeGreaterThan(0);
  for (const td of Array.from(bodyCells)) {
    expect(td.getAttribute("data-label")?.trim()).toBeTruthy();
  }
}

describe("responsive tables (Phase 16 US3)", () => {
  it("members table carries .responsive-table + data-label on every body cell", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (/\/admin\/members\/[^/]+\/tags/.test(url)) return jsonResponse(200, []);
      if (url.includes("/admin/members")) {
        return jsonResponse(200, [
          {
            id: "m1",
            email: "alice@example.com",
            provider: "local_password",
            status: "active",
            is_admin: false,
            created_at: "2026-05-01T00:00:00Z",
          },
        ]);
      }
      return jsonResponse(404, { error: {} });
    });

    const { container } = renderWithProviders(<AdminMembersPage />);
    await waitFor(() => expect(screen.getByText("alice@example.com")).toBeInTheDocument());
    expectResponsiveTableContract(container);
  });

  it("usage table carries .responsive-table + data-label on every body cell", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.includes("/admin/usage/heatmap")) return jsonResponse(200, { cells: [] });
      if (url.includes("group_by=provider")) return jsonResponse(200, { items: [] });
      if (url.includes("/admin/usage")) {
        return jsonResponse(200, {
          group_by: "member",
          items: [
            {
              group_key: "m1",
              display_name: "alice@example.com",
              total_tokens: 1000,
              prompt_tokens: 900,
              completion_tokens: 100,
              reasoning_tokens: 0,
              cached_tokens: 0,
              total_cost_usd: 0.1,
              call_count: 5,
            },
          ],
        });
      }
      return jsonResponse(404, { error: {} });
    });

    const { container } = renderWithProviders(<AdminUsagePage />);
    await waitFor(() => expect(screen.getByText("alice@example.com")).toBeInTheDocument());
    expectResponsiveTableContract(container);
  });
});
