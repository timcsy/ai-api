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

function alloc(over: Record<string, unknown>) {
  return {
    id: "a1", member_id: "m1", subject_snapshot: "u@x.com", resource_model: "azure/m",
    status: "active", quota_tokens_per_month: null, is_service_allocation: false,
    quota_locked: false, token_prefix: "aiapi_x", created_at: "2026-05-24T00:00:00+00:00",
    ...over,
  };
}

function setup(allocations: unknown[]) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const calls: Array<{ url: string; method: string }> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    const method = (init?.method ?? "GET").toUpperCase();
    calls.push({ url, method });
    if (url.endsWith("/admin/allocations") && method === "GET") return jsonResponse(200, allocations);
    if (url.endsWith("/admin/members")) return jsonResponse(200, [{ id: "m1", email: "u@x.com" }]);
    if (url.endsWith("/admin/catalog/models")) return jsonResponse(200, [{ slug: "azure/m" }]);
    if (url.endsWith("/admin/self-service-locks")) return jsonResponse(200, []);
    if (url.includes("/pause") || url.includes("/resume")) return jsonResponse(200, alloc({ status: "active" }));
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

describe("admin allocation pause/resume", () => {
  it("active row offers 暫停 and calls the pause endpoint", async () => {
    const { calls } = setup([alloc({ id: "a1", status: "active" })]);
    await waitFor(() => expect(screen.getByText("azure/m")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "操作" }));
    const item = await screen.findByText(/暫停（可恢復/);
    await userEvent.click(item);
    await waitFor(() =>
      expect(calls.some((c) => c.url.endsWith("/admin/allocations/a1/pause") && c.method === "POST")).toBe(true),
    );
  });

  it("paused row offers 恢復 and calls the resume endpoint", async () => {
    const { calls } = setup([alloc({ id: "a2", status: "paused" })]);
    await waitFor(() => expect(screen.getByText("azure/m")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "操作" }));
    const item = await screen.findByText("恢復");
    await userEvent.click(item);
    await waitFor(() =>
      expect(calls.some((c) => c.url.endsWith("/admin/allocations/a2/resume") && c.method === "POST")).toBe(true),
    );
  });

  it("active row does not offer 恢復", async () => {
    setup([alloc({ id: "a1", status: "active" })]);
    await waitFor(() => expect(screen.getByText("azure/m")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "操作" }));
    await screen.findByText(/暫停（可恢復/);
    expect(screen.queryByText("恢復")).not.toBeInTheDocument();
  });
});
