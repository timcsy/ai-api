import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/contexts/auth";
import { ApplicationsPage } from "@/routes/apps";

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

function setup(allocations: unknown[]) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    calls.push({ url, init });
    if (url.endsWith("/me")) return jsonResponse(200, { id: "m", email: "u@x.com", provider: "local_password" });
    if (url.endsWith("/me/allocations")) return jsonResponse(200, allocations);
    if (url.endsWith("/me/credentials") && init?.method === "POST")
      return jsonResponse(201, { id: "c1", name: "Codex", token: "aiapi_x", token_prefix: "aiapi_x" });
    if (url.endsWith("/me/credentials")) return jsonResponse(200, []);
    return jsonResponse(404, { error: {} });
  });
  render(
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
  return calls;
}

afterEach(() => vi.restoreAllMocks());

describe("Codex create-key shortcut (Phase 27 US2)", () => {
  it("only includes agent-compatible allocations and creates a Codex-scoped key", async () => {
    const calls = setup([AGENT, PLAIN]);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByText("為 Codex 建金鑰")).toBeInTheDocument());
    await user.click(screen.getByText("為 Codex 建金鑰"));
    // picker lists the agent-compatible allocation, NOT the plain one
    await waitFor(() => expect(screen.getByText("Agent GPT")).toBeInTheDocument());
    expect(screen.queryByText("Plain GPT")).not.toBeInTheDocument();
    // create → POST /me/credentials with only the agent allocation id
    await user.click(screen.getByRole("button", { name: "建立" }));
    await waitFor(() => {
      const post = calls.find((c) => c.url.endsWith("/me/credentials") && c.init?.method === "POST");
      expect(post).toBeTruthy();
      const body = JSON.parse(post!.init!.body as string);
      expect(body.allocation_ids).toEqual(["a-agent"]);
    });
  });

  it("shows guidance and no create button when no agent-compatible allocation", async () => {
    setup([PLAIN]);
    await waitFor(() => expect(screen.getByText(/沒有可用於 Codex 的模型/)).toBeInTheDocument());
    expect(screen.queryByText("為 Codex 建金鑰")).not.toBeInTheDocument();
  });
});
