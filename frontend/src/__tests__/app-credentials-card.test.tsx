import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AppCredentialsCard } from "@/components/app-credentials-card";
import { Toaster } from "@/components/ui/toaster";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const CREDS = [
  {
    id: "c1",
    name: "我的筆電",
    token_prefix: "aiapi_aa",
    created_at: "2026-06-01T00:00:00Z",
    last_used_at: null,
    status: "active",
    allocations: [
      { allocation_id: "a1", resource_model: "gpt-4o-mini", display_name: null, status: "active" },
      { allocation_id: "a2", resource_model: "gpt-4o", display_name: null, status: "active" },
    ],
  },
];
const ALLOCS = [
  { id: "a1", resource_model: "gpt-4o-mini", status: "active" },
  { id: "a2", resource_model: "gpt-4o", status: "active" },
];

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AppCredentialsCard />
      <Toaster />
    </QueryClientProvider>,
  );
}

describe("<AppCredentialsCard />", () => {
  it("lists keys with their models and no plaintext", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.endsWith("/me/credentials")) return jsonResponse(200, CREDS);
      if (url.endsWith("/me/allocations")) return jsonResponse(200, ALLOCS);
      return jsonResponse(404, { error: {} });
    });
    renderCard();
    await waitFor(() => expect(screen.getByText("我的筆電")).toBeInTheDocument());
    // both models shown as badges
    expect(screen.getByText("gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByText("gpt-4o")).toBeInTheDocument();
    expect(screen.queryByText(/aiapi_aa[a-z0-9]{6,}/i)).not.toBeInTheDocument();
  });

  it("creates a key by naming it and multi-selecting models, then reveals the token once", async () => {
    const created = {
      id: "c2",
      name: "桌機",
      token: "aiapi_secretsecret",
      token_prefix: "aiapi_bb",
      allocations: [{ allocation_id: "a1", resource_model: "gpt-4o-mini", display_name: null, status: "active" }],
    };
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.endsWith("/me/credentials") && method === "POST") return jsonResponse(201, created);
      if (url.endsWith("/me/credentials")) return jsonResponse(200, CREDS);
      if (url.endsWith("/me/allocations")) return jsonResponse(200, ALLOCS);
      return jsonResponse(404, { error: {} });
    });
    const user = userEvent.setup();
    renderCard();
    await waitFor(() => expect(screen.getByText("我的筆電")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "建立金鑰" }));
    await user.type(screen.getByLabelText("名稱"), "桌機");
    // tick a model checkbox
    const boxes = screen.getAllByRole("checkbox");
    await user.click(boxes[0]!);
    await user.click(screen.getByRole("button", { name: "建立" }));

    await waitFor(() => expect(screen.getByText("aiapi_secretsecret")).toBeInTheDocument());
  });

  it("renames a key via PATCH name (label only)", async () => {
    const calls: { url: string; method: string }[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      const method = (init?.method ?? "GET").toUpperCase();
      calls.push({ url, method });
      if (url.endsWith("/me/credentials/c1") && method === "PATCH") return jsonResponse(200, { ...CREDS[0], name: "改好的名" });
      if (url.endsWith("/me/credentials")) return jsonResponse(200, CREDS);
      if (url.endsWith("/me/allocations")) return jsonResponse(200, ALLOCS);
      return jsonResponse(404, { error: {} });
    });
    const user = userEvent.setup();
    renderCard();
    await waitFor(() => expect(screen.getByText("我的筆電")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "改名" }));
    const input = screen.getByLabelText("名稱");
    await user.clear(input);
    await user.type(input, "改好的名");
    await user.click(screen.getByRole("button", { name: "儲存" }));

    await waitFor(() =>
      expect(calls.some((c) => c.url.endsWith("/me/credentials/c1") && c.method === "PATCH")).toBe(true),
    );
  });
});
