import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { AdminProvidersPage } from "@/routes/admin/providers";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function setup(initial: unknown[]) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const calls: Array<{ url: string; method: string; body?: string }> = [];
  let list = [...initial];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    const method = (init?.method ?? "GET").toUpperCase();
    calls.push({ url, method, body: typeof init?.body === "string" ? init.body : undefined });
    if (url.endsWith("/admin/providers") && method === "GET") {
      return jsonResponse(200, list);
    }
    if (url.endsWith("/admin/providers") && method === "POST") {
      const created = {
        id: "x", provider: "anthropic", label: "primary",
        fingerprint: "deadbeefcafebabe", base_url: null,
        status: "active", last_used_at: null, created_at: "2026-01-01T00:00:00Z",
        created_by: "admin", disabled_at: null, api_key: "sk-ant-test-12345678",
      };
      list = [created, ...list];
      return jsonResponse(201, created);
    }
    return jsonResponse(404, { error: {} });
  });
  return {
    calls,
    ...render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <AdminProvidersPage />
          <Toaster />
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
}

describe("<AdminProvidersPage />", () => {
  it("shows empty state when no credentials", async () => {
    setup([]);
    await waitFor(() =>
      expect(screen.getByText(/尚未加入任何 provider 憑證/)).toBeInTheDocument(),
    );
  });

  it("renders existing credentials with fingerprint and status", async () => {
    setup([
      {
        id: "c1", provider: "openai", label: "prod",
        fingerprint: "abcd1234efgh5678", base_url: null,
        status: "active", last_used_at: null,
        created_at: "2026-01-01T00:00:00Z", created_by: "admin", disabled_at: null,
      },
    ]);
    expect(await screen.findByText("openai")).toBeInTheDocument();
    expect(screen.getByText("prod")).toBeInTheDocument();
    expect(screen.getByText("abcd1234efgh5678")).toBeInTheDocument();
  });

  it("uses Chinese wording for the rotate action (no English Rotate)", async () => {
    setup([
      {
        id: "c1", provider: "openai", label: "prod",
        fingerprint: "abcd1234efgh5678", base_url: null,
        status: "active", last_used_at: null,
        created_at: "2026-01-01T00:00:00Z", created_by: "admin", disabled_at: null,
      },
    ]);
    expect(await screen.findByRole("button", { name: "重新填寫金鑰" })).toBeInTheDocument();
    expect(screen.queryByText("Rotate")).not.toBeInTheDocument();
  });

  it("opens create dialog, submits, then shows plaintext banner", async () => {
    const user = userEvent.setup();
    setup([]);
    await user.click(await screen.findByRole("button", { name: "新增" }));
    await user.type(screen.getByPlaceholderText("team-a-prod"), "primary");
    await user.type(screen.getByPlaceholderText("sk-..."), "sk-ant-test-12345678");
    await user.click(screen.getByRole("button", { name: "建立" }));
    await waitFor(() =>
      expect(screen.getByText(/一次性顯示明文/)).toBeInTheDocument(),
    );
    expect(screen.getByText("sk-ant-test-12345678")).toBeInTheDocument();
  });
});
