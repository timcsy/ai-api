import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MemberUsageCharts } from "@/components/member-usage-charts";
import { presetRange } from "@/lib/time-range";

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
      <MemberUsageCharts range={presetRange("month")} />
    </QueryClientProvider>,
  );
}

describe("MemberUsageCharts (Phase 17)", () => {
  it("renders the daily trend + model donut from /me data", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.includes("/me/usage/timeseries")) {
        return jsonResponse(200, {
          bucket: "day",
          points: [{ ts: "2026-05-10T00:00:00Z", tokens: 1500, cost_usd: 0.15, call_count: 2 }],
        });
      }
      if (url.includes("/me/usage")) {
        return jsonResponse(200, {
          breakdown: [
            { group_key: "azure/m1", display_name: "M1", total_tokens: 1000, total_cost_usd: 0.1, call_count: 1 },
          ],
        });
      }
      return jsonResponse(404, { error: {} });
    });

    const { container } = renderCharts();
    await waitFor(() => {
      const charts = container.querySelectorAll('[data-testid="chart"]');
      expect(charts.length).toBe(2); // daily bar + donut
    });
    expect(screen.getByText("我的每日用量")).toBeInTheDocument();
    expect(screen.getByText("我的各 Model 花費")).toBeInTheDocument();
  });

  it("shows empty states for a member with no usage", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.includes("/me/usage/timeseries")) return jsonResponse(200, { points: [] });
      if (url.includes("/me/usage")) return jsonResponse(200, { breakdown: [] });
      return jsonResponse(404, { error: {} });
    });

    renderCharts();
    expect(await screen.findByText("此區間沒有資料")).toBeInTheDocument();
    expect(await screen.findByText("此區間沒有計費用量")).toBeInTheDocument();
  });
});
