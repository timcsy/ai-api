import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/contexts/auth";
import { DashboardPage } from "@/routes/dashboard";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const ALLOCATIONS = [
  {
    id: "a1", member_id: "m", subject_snapshot: "u@x.com", resource_model: "gpt-4o-mini",
    status: "active", created_at: "2026-05-24T00:00:00+00:00", revoked_at: null,
    token_prefix: "aiapi_x", quota_tokens_per_month: 50000,
  },
  {
    id: "a2", member_id: "m", subject_snapshot: "u@x.com", resource_model: "gpt-4o",
    status: "active", created_at: "2026-05-24T00:00:00+00:00", revoked_at: null,
    token_prefix: "aiapi_y", quota_tokens_per_month: null,
  },
];

const USAGE_BY_ALLOC = {
  from: "2026-05-01T00:00:00+00:00", to: "2026-05-28T00:00:00+00:00",
  summary: { total_tokens: 12000, prompt_tokens: 8000, completion_tokens: 4000, total_cost_usd: 0.5, call_count: 3, has_unpriced: false },
  breakdown: [
    { group_key: "a1", display_name: "u@x.com", total_tokens: 12000, prompt_tokens: 8000, completion_tokens: 4000, total_cost_usd: 0.5, call_count: 3 },
  ],
};

function renderDashboard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.endsWith("/me")) return jsonResponse(200, { id: "m", email: "u@x.com", provider: "local_password" });
    if (url.endsWith("/me/allocations")) return jsonResponse(200, ALLOCATIONS);
    if (url.includes("/me/usage") && url.includes("group_by=allocation")) return jsonResponse(200, USAGE_BY_ALLOC);
    return jsonResponse(404, { error: {} }); // /me/usage?group_by=model (UsageSummary), claimable → degrade
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthProvider queryClient={qc}>
          <Routes>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/dashboard/allocations/:id" element={<div>detail</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("dashboard allocation quota view (US3)", () => {
  it("shows used / quota for a capped allocation", async () => {
    renderDashboard();
    const card = await screen.findByText("gpt-4o-mini").then((el) => el.closest("a")!);
    expect(within(card).getByText(/12,000/)).toBeInTheDocument();
    expect(within(card).getByText(/50,000/)).toBeInTheDocument();
  });

  it("shows unlimited for an allocation without a quota", async () => {
    renderDashboard();
    const card = await screen.findByText("gpt-4o").then((el) => el.closest("a")!);
    expect(within(card).getByText(/無上限/)).toBeInTheDocument();
  });
});
