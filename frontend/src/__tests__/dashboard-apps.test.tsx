import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MemberOverview } from "@/components/member-overview";
import { AuthProvider } from "@/contexts/auth";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function setup(allocations: unknown[]) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.endsWith("/me")) return jsonResponse(200, { id: "m", email: "u@x.com", provider: "local_password" });
    if (url.endsWith("/me/allocations")) return jsonResponse(200, allocations);
    if (url.endsWith("/me/credentials")) return jsonResponse(200, []);
    if (url.endsWith("/me/claimable-models")) return jsonResponse(200, []);
    return jsonResponse(404, { error: {} });
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthProvider queryClient={qc}>
          <Routes>
            <Route path="/dashboard" element={<MemberOverview />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const AGENT = { id: "a1", status: "active", agent_compatible: true };
const PLAIN = { id: "a2", status: "active", agent_compatible: false };

afterEach(() => vi.restoreAllMocks());

describe("dashboard 應用 recommendation (Phase 28)", () => {
  it("recommends Codex when the member has an Agent-compatible model", async () => {
    setup([AGENT]);
    await waitFor(() => expect(screen.getByText("試試 Codex")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /試試 Codex/ })).toHaveAttribute("href", "/apps/codex");
    expect(screen.getByRole("link", { name: /看全部應用/ })).toHaveAttribute("href", "/apps");
  });

  it("does not push Codex when no Agent-compatible model", async () => {
    setup([PLAIN]);
    await waitFor(() => expect(screen.getByRole("link", { name: /看全部應用/ })).toBeInTheDocument());
    expect(screen.queryByText("試試 Codex")).not.toBeInTheDocument();
  });
});
