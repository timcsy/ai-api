import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { AdminAllocationsPage } from "@/routes/admin/allocations";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const ALLOCS = [
  { id: "a1", member_id: "m1", subject_snapshot: "alice@x.com", resource_model: "azure/gpt-4o-mini", status: "active", quota_tokens_per_month: null, quota_cost_usd_per_month: null, is_service_allocation: false, quota_locked: false, token_prefix: "aiapi_a", created_at: "2026-05-24T00:00:00+00:00" },
  { id: "a2", member_id: "m2", subject_snapshot: "bob@x.com", resource_model: "azure/gpt-4o", status: "active", quota_tokens_per_month: null, quota_cost_usd_per_month: null, is_service_allocation: false, quota_locked: false, token_prefix: "aiapi_b", created_at: "2026-05-24T00:00:00+00:00" },
];

function setup(handler?: (url: string, init?: RequestInit) => Response | undefined) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    const method = (init?.method ?? "GET").toUpperCase();
    const custom = handler?.(url, init);
    if (custom) return custom;
    if (url.endsWith("/admin/allocations") && method === "GET") return jsonResponse(200, ALLOCS);
    if (url.endsWith("/admin/members")) return jsonResponse(200, [{ id: "m1", email: "alice@x.com" }, { id: "m2", email: "bob@x.com" }]);
    if (url.endsWith("/admin/catalog/models")) return jsonResponse(200, [{ slug: "azure/gpt-4o-mini" }, { slug: "azure/gpt-4o" }]);
    if (url.endsWith("/admin/self-service-locks")) return jsonResponse(200, []);
    return jsonResponse(404, { error: {} });
  });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AdminAllocationsPage />
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("admin allocations filter + batch", () => {
  it("search narrows rows by member/model", async () => {
    setup();
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByText("alice@x.com")).toBeInTheDocument());
    expect(screen.getByText("bob@x.com")).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText(/搜尋成員/), "alice");
    await waitFor(() => expect(screen.queryByText("bob@x.com")).not.toBeInTheDocument());
    expect(screen.getByText("alice@x.com")).toBeInTheDocument();
  });

  it("batch pause posts selected ids to bulk-action", async () => {
    let body: unknown = null;
    setup((url, init) => {
      if (url.endsWith("/admin/allocations/bulk-action")) {
        body = JSON.parse((init?.body as string) ?? "{}");
        return jsonResponse(200, { changed: 2, failed: 0, results: [] });
      }
      return undefined;
    });
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByText("alice@x.com")).toBeInTheDocument());

    await user.click(screen.getAllByRole("checkbox")[0]!); // header select-all filtered
    expect(screen.getByText(/已選 2/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "批次暫停" }));
    await waitFor(() => expect(body).not.toBeNull());
    expect((body as { action: string }).action).toBe("pause");
    expect((body as { allocation_ids: string[] }).allocation_ids.sort()).toEqual(["a1", "a2"]);
  });

  it("batch quota dialog posts token quota", async () => {
    let body: unknown = null;
    setup((url, init) => {
      if (url.endsWith("/admin/allocations/bulk-quota")) {
        body = JSON.parse((init?.body as string) ?? "{}");
        return jsonResponse(200, { changed: 1, failed: 0, results: [] });
      }
      return undefined;
    });
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByText("alice@x.com")).toBeInTheDocument());

    await user.click(screen.getAllByRole("checkbox")[1]!); // first row
    await user.click(screen.getByRole("button", { name: "批次調配額" }));
    const inputs = await screen.findAllByPlaceholderText("無上限"); // [0]=token (enabled), [1]=cost
    await user.type(inputs[0]!, "5000000");
    await user.click(screen.getByRole("button", { name: "套用" }));
    await waitFor(() => expect(body).not.toBeNull());
    expect((body as { quota_tokens_per_month: number }).quota_tokens_per_month).toBe(5000000);
  });
});
