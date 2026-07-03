import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminRecordsPage } from "@/routes/admin/records";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const RECORDS = {
  items: [
    { id: "a", request_id: "r1", subject: "alice@x.com", model: "azure/gpt-4o", started_at: "2026-07-03T01:00:00Z", finished_at: "2026-07-03T01:00:01Z", status_code: 200, outcome: "success", total_tokens: 120, cost_usd: "0.06", quantity: null, unit: null, error_message: null },
    { id: "b", request_id: "r2", subject: "alice@x.com", model: "azure/gpt-4o", started_at: "2026-07-03T02:00:00Z", finished_at: "2026-07-03T02:00:00Z", status_code: 502, outcome: "upstream_error", total_tokens: 0, cost_usd: null, quantity: null, unit: null, error_message: "boom" },
  ],
  next_before: null,
};

function setup() {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.includes("/admin/members")) return jsonResponse(200, [{ id: "m1", email: "alice@x.com" }]);
    if (url.includes("/admin/records")) return jsonResponse(200, RECORDS);
    return jsonResponse(404, { error: { code: "x", message: "x" } });
  });
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={qc}><AdminRecordsPage /></QueryClientProvider>);
}

afterEach(() => vi.restoreAllMocks());

describe("<AdminRecordsPage /> (spec 056)", () => {
  it("lists per-call records with cost + scatter", async () => {
    setup();
    await waitFor(() => expect(screen.getByRole("heading", { name: "逐筆記錄" })).toBeInTheDocument());
    expect(screen.getByText("逐筆散點")).toBeInTheDocument();
    // priced row shows $, unpriced shows 未定價
    await waitFor(() => expect(screen.getByText("$0.0600")).toBeInTheDocument());
    expect(screen.getByText("未定價")).toBeInTheDocument();
    expect(screen.getByText(/共 2 筆/)).toBeInTheDocument();
  });
});
