import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { UsageSummary } from "@/components/usage-summary";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderUsage(body: unknown, status = 200) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.includes("/me/usage")) return jsonResponse(status, body);
    return jsonResponse(404, { error: {} });
  });
  return render(
    <QueryClientProvider client={qc}>
      <UsageSummary />
    </QueryClientProvider>,
  );
}

const SUMMARY = {
  from: "2026-05-01T00:00:00+00:00",
  to: "2026-05-28T00:00:00+00:00",
  summary: {
    total_tokens: 1500,
    prompt_tokens: 1000,
    completion_tokens: 500,
    total_cost_usd: 1.25,
    call_count: 7,
    has_unpriced: false,
  },
  breakdown: [
    { group_key: "azure/m1", display_name: "M1", total_tokens: 1000, prompt_tokens: 700, completion_tokens: 300, total_cost_usd: 1.0, call_count: 5 },
    { group_key: "azure/m2", display_name: "M2", total_tokens: 500, prompt_tokens: 300, completion_tokens: 200, total_cost_usd: 0.25, call_count: 2 },
  ],
};

describe("<UsageSummary />", () => {
  it("renders total tokens, cost and call count", async () => {
    renderUsage(SUMMARY);
    await waitFor(() => expect(screen.getByText("1,500")).toBeInTheDocument());
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText(/\$1\.25/)).toBeInTheDocument();
  });

  it("shows an under-estimate note when has_unpriced", async () => {
    renderUsage({ ...SUMMARY, summary: { ...SUMMARY.summary, has_unpriced: true } });
    await waitFor(() => expect(screen.getByText(/未定價/)).toBeInTheDocument());
  });

  it("does not show the note when fully priced", async () => {
    renderUsage(SUMMARY);
    await waitFor(() => expect(screen.getByText("1,500")).toBeInTheDocument());
    expect(screen.queryByText(/未定價/)).not.toBeInTheDocument();
  });

  it("shows reasoning/cached breakdown when present", async () => {
    renderUsage({
      ...SUMMARY,
      summary: { ...SUMMARY.summary, reasoning_tokens: 300, cached_tokens: 120 },
    });
    await waitFor(() => expect(screen.getByText(/推理 300 tokens/)).toBeInTheDocument());
    expect(screen.getByText(/快取輸入 120 tokens/)).toBeInTheDocument();
  });

  it("hides reasoning/cached line when both zero", async () => {
    renderUsage({
      ...SUMMARY,
      summary: { ...SUMMARY.summary, reasoning_tokens: 0, cached_tokens: 0 },
    });
    await waitFor(() => expect(screen.getByText("1,500")).toBeInTheDocument());
    expect(screen.queryByText(/推理/)).not.toBeInTheDocument();
  });

  it("degrades quietly on error (renders nothing, no throw)", async () => {
    const { container } = renderUsage({ error: {} }, 500);
    await waitFor(() => expect(screen.queryByText(/載入/)).not.toBeInTheDocument());
    expect(container.querySelector("[data-usage-error]")).toBeNull();
  });
});
