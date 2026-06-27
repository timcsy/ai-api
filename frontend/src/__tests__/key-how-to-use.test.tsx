import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppCredentialsCard } from "@/components/app-credentials-card";
import { Toaster } from "@/components/ui/toaster";

function json(status: number, body: unknown): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const CREDS = [
  {
    id: "c1", name: "我的筆電", token_prefix: "aiapi_aa",
    created_at: "2026-06-01T00:00:00Z", last_used_at: null, status: "active",
    allocations: [
      { allocation_id: "a1", resource_model: "azure/gpt-5.4-mini", display_name: "GPT 5.4 mini", status: "active" },
    ],
  },
];
const ALLOCS = [{ id: "a1", resource_model: "azure/gpt-5.4-mini", status: "active" }];
const CATALOG = [
  { slug: "azure/gpt-5.4-mini", display_name: "GPT 5.4 mini", kind: "chat", responses_support: { state: "available" } },
];

function mockFetch() {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.endsWith("/me/credentials")) return json(200, CREDS);
    if (url.endsWith("/me/allocations")) return json(200, ALLOCS);
    if (url.endsWith("/catalog/models")) return json(200, CATALOG);
    return json(404, { error: {} });
  });
}

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AppCredentialsCard />
      <Toaster />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("key page — 如何使用這把金鑰 (Phase 34)", () => {
  it("each key has a 如何使用 action that opens an example scoped to that key", async () => {
    mockFetch();
    renderCard();
    const btn = await screen.findByRole("button", { name: "如何使用" });
    await userEvent.click(btn);
    // dialog titled after the key + the model selector + the model in the example
    await waitFor(() => expect(screen.getByText("如何使用「我的筆電」")).toBeInTheDocument());
    expect(screen.getByLabelText("選擇模型")).toBeInTheDocument();
    expect(document.body.textContent).toContain("azure/gpt-5.4-mini");
  });
});
