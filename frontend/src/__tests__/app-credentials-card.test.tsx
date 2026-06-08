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

  it("hides revoked keys by default and reveals them with the 含已撤回 toggle", async () => {
    const withRevoked = [
      CREDS[0],
      {
        id: "c9", name: "舊裝置", token_prefix: "aiapi_zz",
        created_at: "2026-05-01T00:00:00Z", last_used_at: null, status: "revoked",
        allocations: [{ allocation_id: "a1", resource_model: "gpt-4o-mini", display_name: null, status: "active" }],
      },
    ];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.endsWith("/me/credentials")) return jsonResponse(200, withRevoked);
      if (url.endsWith("/me/allocations")) return jsonResponse(200, ALLOCS);
      return jsonResponse(404, { error: {} });
    });
    const user = userEvent.setup();
    renderCard();
    await waitFor(() => expect(screen.getByText("我的筆電")).toBeInTheDocument());
    // revoked key hidden by default
    expect(screen.queryByText("舊裝置")).not.toBeInTheDocument();
    // toggle reveals it
    await user.click(screen.getByRole("switch", { name: /含已撤回/ }));
    await waitFor(() => expect(screen.getByText("舊裝置")).toBeInTheDocument());
  });

  it("has a single 編輯 action (no separate 改名 / 編輯 model)", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.endsWith("/me/credentials")) return jsonResponse(200, CREDS);
      if (url.endsWith("/me/allocations")) return jsonResponse(200, ALLOCS);
      return jsonResponse(404, { error: {} });
    });
    renderCard();
    await waitFor(() => expect(screen.getByText("我的筆電")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "編輯" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "改名" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "編輯 model" })).not.toBeInTheDocument();
  });

  it("edits name + model in one dialog, sending a single PATCH with both", async () => {
    let patchBody: Record<string, unknown> | null = null;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.endsWith("/me/credentials/c1") && method === "PATCH") {
        patchBody = JSON.parse(String(init?.body ?? "{}"));
        return jsonResponse(200, { ...CREDS[0], name: "改好的名" });
      }
      if (url.endsWith("/me/credentials")) return jsonResponse(200, CREDS);
      if (url.endsWith("/me/allocations")) return jsonResponse(200, ALLOCS);
      return jsonResponse(404, { error: {} });
    });
    const user = userEvent.setup();
    renderCard();
    await waitFor(() => expect(screen.getByText("我的筆電")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "編輯" }));
    const input = screen.getByLabelText("名稱");
    await user.clear(input);
    await user.type(input, "改好的名");
    // untick the second model (a2 → remove)
    const boxes = screen.getAllByRole("checkbox");
    await user.click(boxes[1]!);
    await user.click(screen.getByRole("button", { name: "儲存" }));

    await waitFor(() => expect(patchBody).not.toBeNull());
    expect(patchBody).toMatchObject({ name: "改好的名", remove: ["a2"] });
  });
});
