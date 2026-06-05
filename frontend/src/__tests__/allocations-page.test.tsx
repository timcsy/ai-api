import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/contexts/auth";
import { AllocationsPage } from "@/routes/allocations";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const ALLOC = {
  id: "a1", member_id: "m", subject_snapshot: "u@x.com", resource_model: "gpt-4o-mini",
  display_name: "GPT-4o mini", status: "active", created_at: "2026-05-24T00:00:00+00:00",
  revoked_at: null, token_prefix: "aiapi_x", quota_tokens_per_month: null, price: null,
};

function renderAllocations(allocations: unknown[] = [ALLOC]) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.endsWith("/me")) return jsonResponse(200, { id: "m", email: "u@x.com", provider: "local_password" });
    if (url.endsWith("/me/allocations")) return jsonResponse(200, allocations);
    return jsonResponse(404, { error: {} });
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/allocations"]}>
        <AuthProvider queryClient={qc}>
          <Routes>
            <Route path="/allocations" element={<AllocationsPage />} />
            <Route path="/dashboard/allocations/:id" element={<div>detail</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("<AllocationsPage /> (Phase 22 US1/US3)", () => {
  it("renders the member's allocation cards", async () => {
    renderAllocations();
    expect(await screen.findByText("我的分配")).toBeInTheDocument();
    expect(await screen.findByText("GPT-4o mini")).toBeInTheDocument();
  });

  it("shows the 分配 vs 金鑰 one-line explainer", async () => {
    renderAllocations([]);
    await waitFor(() =>
      expect(screen.getByText(/拿來連線的鑰匙/)).toBeInTheDocument(),
    );
  });
});
