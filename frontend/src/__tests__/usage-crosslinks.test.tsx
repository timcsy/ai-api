import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MemberOverview } from "@/components/member-overview";
import { AuthProvider } from "@/contexts/auth";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const ME = { id: "m", email: "alice@x.com", provider: "local_password" };
const CREDS = [{
  id: "c1", name: "我的筆電", token_prefix: "aiapi_aa", created_at: "2026-06-01T00:00:00Z",
  last_used_at: null, status: "active",
  allocations: [{ allocation_id: "a1", resource_model: "azure/gpt-5.4-mini", display_name: null, status: "active" }],
}];

afterEach(() => vi.restoreAllMocks());

describe("dashboard cross-link to 如何呼叫 (Phase 34)", () => {
  it("once the member has a key, points to how to start calling", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.endsWith("/me")) return json(200, ME);
      if (url.endsWith("/me/credentials")) return json(200, CREDS);
      if (url.endsWith("/me/allocations")) return json(200, []);
      if (url.endsWith("/me/claimable-models")) return json(200, []);
      return json(200, {});
    });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/dashboard"]}>
          <AuthProvider queryClient={qc}>
            <MemberOverview />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const link = await screen.findByRole("link", { name: "怎麼開始呼叫 →" });
    expect(link).toHaveAttribute("href", "/keys");
  });
});
