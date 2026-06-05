import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/contexts/auth";
import { DashboardPage } from "@/routes/dashboard";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const ME = { id: "m", email: "alice@x.com", provider: "local_password" };

function renderDashboard(opts: {
  allocations?: unknown[];
  credentials?: unknown[];
  claimable?: unknown[];
} = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.endsWith("/me")) return jsonResponse(200, ME);
    if (url.endsWith("/me/allocations")) return jsonResponse(200, opts.allocations ?? []);
    if (url.endsWith("/me/credentials")) return jsonResponse(200, opts.credentials ?? []);
    if (url.endsWith("/me/claimable-models")) return jsonResponse(200, opts.claimable ?? []);
    return jsonResponse(404, { error: {} }); // /me/usage* → UsageSummary degrades quietly
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthProvider queryClient={qc}>
          <Routes>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/keys" element={<div data-testid="keys">keys</div>} />
            <Route path="/allocations" element={<div data-testid="allocations">allocs</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("<DashboardPage /> slim overview (Phase 22 US2)", () => {
  it("shows active key and allocation counts, not full management widgets", async () => {
    renderDashboard({
      allocations: [
        { id: "a1", status: "active" },
        { id: "a2", status: "revoked" },
      ],
      credentials: [{ id: "c1", status: "active" }],
    });
    await waitFor(() => expect(screen.getByText("活躍金鑰")).toBeInTheDocument());
    expect(screen.getByText("活躍分配")).toBeInTheDocument();
    // counts: 1 active key, 1 active allocation
    expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(2);
    // management widgets are NOT on the overview
    expect(screen.queryByText("可用 model")).not.toBeInTheDocument(); // credentials table header
    expect(screen.queryByText("用量圖表")).not.toBeInTheDocument(); // usage charts heading
    expect(screen.queryByText("我的分配")).not.toBeInTheDocument(); // allocation list heading
  });

  it("nudges to create a key when the member has none, linking to /keys", async () => {
    renderDashboard({ credentials: [] });
    const link = await screen.findByRole("link", { name: /去建立金鑰/ });
    expect(link).toHaveAttribute("href", "/keys");
  });

  it("nudges to claim when claimable models exist, linking to /allocations", async () => {
    renderDashboard({
      credentials: [{ id: "c1", status: "active" }],
      claimable: [{ state: "claimable" }],
    });
    const link = await screen.findByRole("link", { name: /去領取/ });
    expect(link).toHaveAttribute("href", "/allocations");
  });
});
