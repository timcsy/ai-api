import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/contexts/auth";
import { APPLICATIONS } from "@/lib/applications";
import { ApplicationsPage } from "@/routes/apps";
import { AppDetailPage } from "@/routes/app-detail";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const AGENT = {
  id: "a-agent", resource_model: "azure/agent", display_name: "Agent GPT",
  status: "active", agent_compatible: true,
};
const PLAIN = {
  id: "a-plain", resource_model: "azure/plain", display_name: "Plain GPT",
  status: "active", agent_compatible: false,
};

function setupDetail(allocations: unknown[]) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.endsWith("/me")) return jsonResponse(200, { id: "m", email: "u@x.com", provider: "local_password" });
    if (url.endsWith("/me/allocations")) return jsonResponse(200, allocations);
    if (url.endsWith("/me/credentials")) return jsonResponse(200, []);
    return jsonResponse(404, { error: {} });
  });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/apps/copilot"]}>
        <AuthProvider queryClient={qc}>
          <Routes>
            <Route path="/apps/:appId" element={<AppDetailPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("應用商店 — GitHub Copilot (Phase 36 / spec 050)", () => {
  it("registry includes the copilot app", () => {
    expect(APPLICATIONS.map((a) => a.id)).toContain("copilot");
  });

  it("apps page shows the GitHub Copilot tile", () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/apps"]}>
          <ApplicationsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByText("GitHub Copilot")).toBeInTheDocument();
  });

  it("detail renders setup + create-key shortcut when an agent-compatible allocation exists", async () => {
    setupDetail([AGENT]);
    await waitFor(() => expect(screen.getByRole("heading", { name: "GitHub Copilot" })).toBeInTheDocument());
    expect(screen.getByText("為 Copilot 建金鑰")).toBeInTheDocument();
  });

  it("shows guidance and no create button when no agent-compatible allocation", async () => {
    setupDetail([PLAIN]);
    await waitFor(() => expect(screen.getByText(/沒有可用於 Copilot 的模型/)).toBeInTheDocument());
    expect(screen.queryByText("為 Copilot 建金鑰")).not.toBeInTheDocument();
  });

  it("explains the per-allocation conversation caveat (US3)", async () => {
    setupDetail([AGENT]);
    await waitFor(() => expect(screen.getByRole("heading", { name: "GitHub Copilot" })).toBeInTheDocument());
    expect(screen.getByText(/跨 model 切換.*開新對話|開新對話/)).toBeInTheDocument();
  });
});
