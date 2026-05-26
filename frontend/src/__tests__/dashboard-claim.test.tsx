import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { AuthProvider } from "@/contexts/auth";
import { DashboardPage } from "@/routes/dashboard";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const ME = { id: "m", email: "alice@x.com", provider: "local_password" };

function mountWithClaimable(claimable: unknown) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    const method = (init?.method ?? "GET").toUpperCase();
    if (url.endsWith("/me")) return jsonResponse(200, ME);
    if (url.endsWith("/me/allocations") && method === "GET") return jsonResponse(200, []);
    if (url.endsWith("/me/claimable-models")) return jsonResponse(200, claimable);
    if (url.endsWith("/me/allocations") && method === "POST")
      return jsonResponse(201, { token: "aiapi_SECRET_TOKEN_123", allocation: { id: "a1" } });
    return jsonResponse(404, { error: {} });
  });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthProvider queryClient={qc}>
          <Routes>
            <Route path="/dashboard" element={<DashboardPage />} />
          </Routes>
          <Toaster />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("<DashboardPage /> self-service claim", () => {
  it("claims a credential and reveals the one-time token", async () => {
    mountWithClaimable([
      { slug: "azure/gpt-5.4-mini", display_name: "GPT-5.4 mini", provider: "azure", default_quota: 50000, state: "claimable" },
    ]);
    const btn = await screen.findByRole("button", { name: "領取憑證" });
    await userEvent.click(btn);
    await waitFor(() =>
      expect(screen.getByText(/此 token 只顯示一次/)).toBeInTheDocument(),
    );
    expect(screen.getByText("aiapi_SECRET_TOKEN_123")).toBeInTheDocument();
  });

  it("shows 已領取 / 需 admin 解鎖 states without a claim button", async () => {
    mountWithClaimable([
      { slug: "azure/a", display_name: "A", provider: "azure", default_quota: 100, state: "already_claimed" },
      { slug: "azure/b", display_name: "B", provider: "azure", default_quota: 100, state: "reclaim_locked" },
    ]);
    await waitFor(() => expect(screen.getByText("已領取")).toBeInTheDocument());
    expect(screen.getByText("需 admin 解鎖")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "領取憑證" })).not.toBeInTheDocument();
  });

  it("hides the section when nothing is claimable", async () => {
    mountWithClaimable([]);
    await waitFor(() => expect(screen.getByText(/尚未獲得任何分配/)).toBeInTheDocument());
    expect(screen.queryByText("可自助領取")).not.toBeInTheDocument();
  });
});
