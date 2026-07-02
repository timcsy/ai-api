import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminAnomalyPage } from "@/routes/admin/anomaly";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const CONFIG = {
  auto_quarantine_enabled: true,
  pause_until: null,
  effective_enforcing: true,
  status: "enabled",
  thresholds: { threshold_multiplier: 10, min_calls: 100, absolute_cold_start: 10000, baseline_min_calls: 200 },
  updated_at: null,
  updated_by: null,
};

function setup() {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    calls.push({ url, init });
    if (url.endsWith("/admin/anomaly/config") && (!init || init.method === "GET" || !init.method))
      return jsonResponse(200, CONFIG);
    if (url.endsWith("/admin/anomaly/config") && init?.method === "PUT")
      return jsonResponse(200, { ...CONFIG, auto_quarantine_enabled: false, status: "disabled", effective_enforcing: false });
    return jsonResponse(404, { error: { code: "x", message: "x" } });
  });
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <AdminAnomalyPage />
    </QueryClientProvider>,
  );
  return calls;
}

afterEach(() => vi.restoreAllMocks());

describe("<AdminAnomalyPage /> (spec 054)", () => {
  it("shows status + the disable switch and threshold fields", async () => {
    setup();
    await waitFor(() => expect(screen.getByText("啟用中")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "停用自動隔離" })).toBeInTheDocument();
    expect(screen.getByLabelText(/暫停到此時間/)).toBeInTheDocument();
    expect(screen.getByLabelText(/baseline 最小可信樣本數/)).toBeInTheDocument();
  });

  it("disabling auto-quarantine PUTs the switch", async () => {
    const calls = setup();
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByRole("button", { name: "停用自動隔離" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "停用自動隔離" }));
    await waitFor(() => {
      const put = calls.find((c) => c.url.endsWith("/admin/anomaly/config") && c.init?.method === "PUT");
      expect(put).toBeTruthy();
      expect(JSON.parse(put!.init!.body as string)).toEqual({ auto_quarantine_enabled: false });
    });
  });
});
