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

const ALLOC = {
  id: "a1", member_id: "m1", subject_snapshot: "u@x.com", resource_model: "azure/m",
  status: "active", quota_tokens_per_month: 50000, is_service_allocation: false,
  quota_locked: false, token_prefix: "aiapi_x", created_at: "2026-05-24T00:00:00+00:00",
};

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const calls: Array<{ url: string; method: string; body?: string }> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    const method = (init?.method ?? "GET").toUpperCase();
    calls.push({ url, method, body: typeof init?.body === "string" ? init.body : undefined });
    if (url.endsWith("/admin/allocations") && method === "GET") return jsonResponse(200, [ALLOC]);
    if (url.endsWith("/admin/members")) return jsonResponse(200, [{ id: "m1", email: "u@x.com" }]);
    if (url.endsWith("/admin/catalog/models")) return jsonResponse(200, [{ slug: "azure/m" }]);
    if (url.endsWith("/admin/self-service-locks")) return jsonResponse(200, []);
    if (url.includes("/admin/allocations/a1") && method === "PATCH") return jsonResponse(200, ALLOC);
    return jsonResponse(404, { error: {} });
  });
  return {
    calls,
    ...render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <AdminAllocationsPage />
          <Toaster />
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
}

async function openQuotaDialog() {
  await waitFor(() => expect(screen.getByText("azure/m")).toBeInTheDocument());
  await userEvent.click(screen.getByRole("button", { name: "操作" }));
  await userEvent.click(await screen.findByText("調整配額"));
  return screen.getByRole("spinbutton", { name: "月度配額" });
}

describe("admin quota adjust dialog (US5)", () => {
  it("opens an in-app dialog prefilled with the current quota", async () => {
    setup();
    const input = await openQuotaDialog();
    expect(input).toHaveValue(50000);
  });

  it("submits a valid quota via PATCH", async () => {
    const { calls } = setup();
    const input = await openQuotaDialog();
    await userEvent.clear(input);
    await userEvent.type(input, "12345");
    await userEvent.click(screen.getByRole("button", { name: "套用" }));
    await waitFor(() => {
      const patch = calls.find((c) => c.url.includes("/admin/allocations/a1") && c.method === "PATCH");
      expect(patch).toBeTruthy();
      expect(patch!.body).toContain("12345");
    });
  });

  it("treats empty as unlimited (null)", async () => {
    const { calls } = setup();
    const input = await openQuotaDialog();
    await userEvent.clear(input);
    await userEvent.click(screen.getByRole("button", { name: "套用" }));
    await waitFor(() => {
      const patch = calls.find((c) => c.url.includes("/admin/allocations/a1") && c.method === "PATCH");
      expect(patch!.body).toContain("null");
    });
  });
});
