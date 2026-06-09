import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/contexts/auth";
import { ApplicationsPage } from "@/routes/apps";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function renderApps(allocations: unknown[] = []) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.endsWith("/me")) return jsonResponse(200, { id: "m", email: "u@x.com", provider: "local_password" });
    if (url.endsWith("/me/allocations")) return jsonResponse(200, allocations);
    if (url.endsWith("/me/credentials")) return jsonResponse(200, []);
    return jsonResponse(404, { error: {} });
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/apps"]}>
        <AuthProvider queryClient={qc}>
          <Routes>
            <Route path="/apps" element={<ApplicationsPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("<ApplicationsPage /> (Phase 27)", () => {
  it("renders the Codex application card with the one-click install", async () => {
    renderApps();
    await waitFor(() => expect(screen.getByText("應用")).toBeInTheDocument());
    // Codex card heading + the existing one-line install card
    expect(screen.getByText("Codex")).toBeInTheDocument();
    expect(screen.getByText(/安裝 Codex/)).toBeInTheDocument();
  });
});
