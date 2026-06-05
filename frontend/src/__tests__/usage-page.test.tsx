import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/contexts/auth";
import { UsagePage } from "@/routes/usage";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const USAGE = {
  from: "2026-05-01T00:00:00+00:00", to: "2026-05-28T00:00:00+00:00",
  summary: {
    total_tokens: 1000, prompt_tokens: 600, completion_tokens: 400, reasoning_tokens: 0,
    cached_tokens: 0, total_cost_usd: 0.12, call_count: 5, has_unpriced: false,
  },
  breakdown: [],
};

function renderUsage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.endsWith("/me")) return jsonResponse(200, { id: "m", email: "u@x.com", provider: "local_password" });
    if (url.includes("/me/usage")) return jsonResponse(200, USAGE);
    return jsonResponse(404, { error: {} });
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/usage"]}>
        <AuthProvider queryClient={qc}>
          <Routes>
            <Route path="/usage" element={<UsagePage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("<UsagePage /> (Phase 22 US1)", () => {
  it("renders the usage summary and the charts heading", async () => {
    renderUsage();
    await waitFor(() => expect(screen.getByText("用量總覽")).toBeInTheDocument());
    expect(screen.getByText("用量圖表")).toBeInTheDocument();
  });
});
