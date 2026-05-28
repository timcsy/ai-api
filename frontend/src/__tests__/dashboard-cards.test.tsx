import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/contexts/auth";
import { DashboardPage } from "@/routes/dashboard";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function setup(allocations: unknown[], claimable: unknown[] = []) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.endsWith("/me")) return jsonResponse(200, { id: "m", email: "u@x.com", provider: "local_password" });
    if (url.endsWith("/me/allocations")) return jsonResponse(200, allocations);
    if (url.endsWith("/me/claimable-models")) return jsonResponse(200, claimable);
    return jsonResponse(404, { error: {} }); // /me/usage* → degrade
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthProvider queryClient={qc}>
          <Routes>
            <Route path="/dashboard" element={<DashboardPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const ALLOC = {
  id: "a1", member_id: "m", subject_snapshot: "u@x.com", resource_model: "azure/gpt-5.4-mini",
  display_name: "GPT-5.4 mini", status: "active", created_at: "2026-05-24T00:00:00+00:00",
  revoked_at: null, token_prefix: "aiapi_x", quota_tokens_per_month: null,
  price: { input_per_1k: "0.00015", output_per_1k: "0.0006" },
};

describe("dashboard allocation cards (US1)", () => {
  it("shows display_name as title and slug as secondary", async () => {
    setup([ALLOC]);
    await waitFor(() => expect(screen.getByText("GPT-5.4 mini")).toBeInTheDocument());
    expect(screen.getByText(/azure\/gpt-5\.4-mini/)).toBeInTheDocument();
  });

  it("shows current price per 1M", async () => {
    setup([ALLOC]);
    // 0.00015 per 1k → 0.15 per 1m ; 0.0006 → 0.6
    await waitFor(() => expect(screen.getByText(/輸入 \$0\.15/)).toBeInTheDocument());
    expect(screen.getByText(/輸出 \$0\.6/)).toBeInTheDocument();
  });

  it("shows 未定價 when price is null", async () => {
    setup([{ ...ALLOC, price: null }]);
    await waitFor(() => expect(screen.getByText("未定價")).toBeInTheDocument());
  });

  it("falls back to slug when display_name is null", async () => {
    setup([{ ...ALLOC, display_name: null }]);
    await waitFor(() =>
      expect(screen.getAllByText(/azure\/gpt-5\.4-mini/).length).toBeGreaterThan(0),
    );
  });
});

describe("dashboard onboarding (US3)", () => {
  it("shows the 3-step guide when there are no allocations", async () => {
    setup([]);
    await waitFor(() => expect(screen.getByText(/① 領取憑證/)).toBeInTheDocument());
    expect(screen.getByText(/② 複製/)).toBeInTheDocument();
    expect(screen.getByText(/③ 貼進 Authorization/)).toBeInTheDocument();
  });

  it("does not show the guide once there is an allocation", async () => {
    setup([ALLOC]);
    await waitFor(() => expect(screen.getByText("GPT-5.4 mini")).toBeInTheDocument());
    expect(screen.queryByText(/① 領取憑證/)).not.toBeInTheDocument();
  });
});

describe("dashboard token hint (US6)", () => {
  it("mentions self-service in the token hint", async () => {
    setup([]);
    await waitFor(() => expect(screen.getByText(/自助領取/)).toBeInTheDocument());
  });
});

describe("claimable card links to model detail (US2)", () => {
  it("renders the claimable card as a link to /catalog/{slug}", async () => {
    setup([], [{ slug: "azure/m9", display_name: "M9", provider: "azure", default_quota: 50000, state: "claimable" }]);
    const link = await screen.findByRole("link", { name: /M9/ });
    expect(link).toHaveAttribute("href", "/catalog/azure/m9");
  });
});
