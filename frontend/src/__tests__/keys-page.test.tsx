import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/contexts/auth";
import { KeysPage } from "@/routes/keys";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function renderKeys() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.endsWith("/me")) return jsonResponse(200, { id: "m", email: "u@x.com", provider: "local_password" });
    if (url.endsWith("/me/credentials")) return jsonResponse(200, []);
    if (url.endsWith("/me/allocations")) return jsonResponse(200, []);
    return jsonResponse(404, { error: {} });
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/keys"]}>
        <AuthProvider queryClient={qc}>
          <Routes>
            <Route path="/keys" element={<KeysPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("<KeysPage /> (Phase 22 US1/US3)", () => {
  it("renders API endpoint card, the app-credentials section, and Codex install", async () => {
    renderKeys();
    await waitFor(() => expect(screen.getByText("API 端點")).toBeInTheDocument());
    expect(screen.getByText("我的應用 / 金鑰")).toBeInTheDocument();
    expect(screen.getByText(/自助領取/)).toBeInTheDocument(); // one-time-token hint
  });

  it("shows the 分配 vs 金鑰 one-line explainer", async () => {
    renderKeys();
    await waitFor(() =>
      expect(screen.getByText(/拿來連線的鑰匙/)).toBeInTheDocument(),
    );
  });
});
