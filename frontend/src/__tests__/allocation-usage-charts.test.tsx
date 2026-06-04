import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AllocationUsageCharts } from "@/components/allocation-usage-charts";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderCharts() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AllocationUsageCharts allocationId="a1" />
    </QueryClientProvider>,
  );
}

describe("<AllocationUsageCharts />", () => {
  it("renders the per-allocation trend + heatmap from /me/allocations/{id}/usage", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.includes("/me/allocations/a1/usage/timeseries")) {
        return jsonResponse(200, {
          bucket: "day",
          points: [{ ts: "2026-05-10T00:00:00Z", tokens: 1500, cost_usd: 0.15, call_count: 2 }],
        });
      }
      if (url.includes("/me/allocations/a1/usage/heatmap")) {
        return jsonResponse(200, {
          timezone: "UTC+8",
          cells: [{ weekday: 1, hour: 9, tokens: 1500, call_count: 2 }],
        });
      }
      return jsonResponse(404, { error: {} });
    });

    const { container } = renderCharts();
    expect(screen.getByText("這筆分配的用量")).toBeInTheDocument();

    // Heatmap renders plain divs; the populated cell carries a descriptive title.
    await waitFor(() => {
      expect(container.querySelector('[title*="1,500 tokens"]')).toBeTruthy();
    });
  });

  it("shows the heatmap empty state when there is no usage", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.includes("/usage/timeseries")) return jsonResponse(200, { points: [] });
      if (url.includes("/usage/heatmap")) return jsonResponse(200, { timezone: "UTC+8", cells: [] });
      return jsonResponse(404, { error: {} });
    });

    renderCharts();
    // Both the line chart and the heatmap surface an empty state for no usage.
    await waitFor(() => {
      expect(screen.getAllByText("此區間沒有資料").length).toBeGreaterThanOrEqual(1);
    });
  });
});
