import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminQuotaPoolPage } from "@/routes/admin/quota-pool";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const STATUS = {
  total_T: 0,
  reserved: { service: 0, locked: 0 },
  distributable: 0,
  pool_member_count: 2,
  floor: 1000,
  settings: { enabled: false },
  last_rebalance_at: null,
  config: { total_tokens_per_month: 0, floor_per_allocation: 1000, updated_at: null, updated_by: null },
  suggestion: {
    recent_month_tokens: 1_000_000,
    pool_members: 2,
    suggested_total: 2_000_000,
    suggested_floor: 500_000,
  },
  warning: null,
};

function setup() {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    calls.push({ url, init });
    if (url.endsWith("/admin/quota-pool/status")) return jsonResponse(200, STATUS);
    if (url.includes("/admin/quota-pool/rebalance-log")) return jsonResponse(200, []);
    if (url.endsWith("/admin/quota-pool/config") && init?.method === "PUT")
      return jsonResponse(200, { total_tokens_per_month: 2_000_000, floor_per_allocation: 500_000, warning: null });
    return jsonResponse(404, { error: { code: "x", message: "x" } });
  });
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <AdminQuotaPoolPage />
    </QueryClientProvider>,
  );
  return calls;
}

afterEach(() => vi.restoreAllMocks());

describe("<AdminQuotaPoolPage /> config editor (Phase 39)", () => {
  it("shows the editable config form and the suggestion with reasoning", async () => {
    setup();
    await waitFor(() => expect(screen.getByText("配額池設定")).toBeInTheDocument());
    expect(screen.getByLabelText(/每月總額 T/)).toBeInTheDocument();
    expect(screen.getByLabelText(/每分配保底/)).toBeInTheDocument();
    // suggestion + reasoning
    expect(screen.getByText(/建議值/)).toBeInTheDocument();
    expect(screen.getByText(/留成長空間又封住總量上限/)).toBeInTheDocument();
  });

  it("blocks save when T < floor × N, and the apply-suggestion button fixes it", async () => {
    setup();
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByText("配額池設定")).toBeInTheDocument());
    // current config T=0, floor=1000, N=2 → 0 < 2000 → save disabled + error
    expect(screen.getByRole("button", { name: "儲存設定" })).toBeDisabled();
    expect(screen.getByText(/總額需/)).toBeInTheDocument();
    // apply suggestion (T=2,000,000, floor=500,000 → 2M ≥ 1M) → save enabled
    await user.click(screen.getByRole("button", { name: "套用建議" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "儲存設定" })).toBeEnabled());
  });

  it("saves via PUT /admin/quota-pool/config", async () => {
    const calls = setup();
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByText("配額池設定")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "套用建議" }));
    await user.click(screen.getByRole("button", { name: "儲存設定" }));
    await waitFor(() => {
      const put = calls.find((c) => c.url.endsWith("/admin/quota-pool/config") && c.init?.method === "PUT");
      expect(put).toBeTruthy();
      expect(JSON.parse(put!.init!.body as string)).toEqual({
        total_tokens_per_month: 2_000_000,
        floor_per_allocation: 500_000,
      });
    });
  });
});
