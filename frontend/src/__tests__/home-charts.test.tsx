import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AdminHomePage } from "@/routes/admin/home";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// Dashboard mode requires ≥1 active provider/model/member/allocation. Seed those
// plus one quarantined allocation so we can assert the alert sits above charts.
function mockFetch(opts: { vizEmpty?: boolean } = {}) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.includes("/admin/providers"))
      return jsonResponse(200, [{ id: "p1", provider: "azure", status: "active" }]);
    if (url.includes("/admin/members"))
      return jsonResponse(200, [{ id: "m1", status: "active" }]);
    if (url.includes("/admin/catalog/models"))
      return jsonResponse(200, [
        {
          slug: "gpt-4o-mini",
          visibility: {
            provider_has_credential: true,
            visible_member_count: 1,
            total_active_members: 1,
          },
        },
      ]);
    if (url.includes("/admin/allocations"))
      return jsonResponse(200, [
        { id: "a1", status: "active" },
        { id: "a2", status: "quarantined" },
      ]);
    if (url.includes("/admin/audit")) return jsonResponse(200, { rows: [] });
    if (url.includes("/admin/system/info"))
      return jsonResponse(200, { request_body_limit_mb: 10 });
    // viz endpoints
    if (url.includes("/admin/usage/timeseries"))
      return jsonResponse(200, { points: opts.vizEmpty ? [] : [] });
    if (url.includes("/admin/usage"))
      return jsonResponse(200, { items: [] });
    return jsonResponse(404, { error: {} });
  });
}

function renderHome() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AdminHomePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("admin home charts (Phase 14 US1)", () => {
  it("renders at most three charts", async () => {
    mockFetch();
    renderHome();
    await waitFor(() =>
      expect(screen.getByText(/管理員儀表板/)).toBeInTheDocument(),
    );
    const charts = await screen.findAllByTestId("chart");
    expect(charts.length).toBeLessThanOrEqual(3);
    expect(charts.length).toBe(3);
  });

  it("places the quarantine alert before the charts in the DOM", async () => {
    mockFetch();
    renderHome();
    const alert = await screen.findByText(/個分配被自動隔離/);
    const charts = await screen.findAllByTestId("chart");
    const firstChart = charts[0];
    expect(firstChart).toBeDefined();
    // alert must come before the first chart
    const pos = alert.compareDocumentPosition(firstChart as Node);
    expect(pos & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("shows the empty state when there is no usage data", async () => {
    mockFetch({ vizEmpty: true });
    renderHome();
    expect(await screen.findByText("此區間沒有計費用量")).toBeInTheDocument();
    expect((await screen.findAllByText("此區間沒有資料")).length).toBeGreaterThan(0);
  });
});
