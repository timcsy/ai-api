import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AllocationKeysReadonly } from "@/components/allocation-keys-readonly";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const CREDS = [
  {
    id: "c1", name: "我的筆電", token_prefix: "aiapi_aa", status: "active",
    allocations: [
      { allocation_id: "a1", resource_model: "gpt-4o-mini", display_name: null, status: "active" },
      { allocation_id: "a2", resource_model: "gpt-4o", display_name: null, status: "active" },
    ],
  },
  {
    id: "c2", name: "別把", token_prefix: "aiapi_bb", status: "active",
    allocations: [{ allocation_id: "a9", resource_model: "other", display_name: null, status: "active" }],
  },
];

function renderView() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(200, CREDS));
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AllocationKeysReadonly allocationId="a1" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("<AllocationKeysReadonly />", () => {
  it("lists only keys whose scope includes this model, shows their full model set, no manage buttons", async () => {
    renderView();
    // c1 covers a1 → shown; c2 (a9 only) → not shown.
    await waitFor(() => expect(screen.getByText("我的筆電")).toBeInTheDocument());
    expect(screen.queryByText("別把")).not.toBeInTheDocument();
    // shows the key's FULL set of models (so cross-model effect is visible)
    expect(screen.getByText("gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByText("gpt-4o")).toBeInTheDocument();
    // read-only: no manage actions
    expect(screen.queryByRole("button", { name: "撤回" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重新產生" })).not.toBeInTheDocument();
    // link to the single management surface
    expect(screen.getByRole("link", { name: "前往管理" })).toBeInTheDocument();
  });
});
