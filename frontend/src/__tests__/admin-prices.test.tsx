import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { AdminPricesPage } from "@/routes/admin/prices";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AdminPricesPage />
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

const ROWS = [
  {
    provider: "azure", model: "gpt-4o-mini", slug: "azure/gpt-4o-mini",
    display_name: "GPT-4o mini", priced: true, in_catalog: true,
    current: { input_per_1k: "0.0001", output_per_1k: "0.0006", effective_from: "2026-05-01T00:00:00Z" },
  },
  {
    provider: "azure", model: "gpt-5.4-mini", slug: "azure/gpt-5.4-mini",
    display_name: "GPT-5.4 mini", priced: false, in_catalog: true, current: null,
  },
];

describe("<AdminPricesPage />", () => {
  it("renders priced rows and 未定價 badge", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(200, ROWS));
    renderPage();
    expect(await screen.findByText("azure/gpt-4o-mini")).toBeInTheDocument();
    // default display unit is per-1M: 0.0001/1K → 0.1/1M
    expect(screen.getByText("$0.1")).toBeInTheDocument();
    expect(screen.getByText("未定價")).toBeInTheDocument();
  });

  it("converts per-1M input to per-1K and surfaces duplicate_version error", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    fetchMock.mockResolvedValueOnce(jsonResponse(200, ROWS)); // list
    let posted: any = null;
    fetchMock.mockImplementationOnce(async (_url, init) => {
      posted = JSON.parse((init?.body as string) ?? "{}");
      return jsonResponse(409, { detail: { error: { code: "duplicate_version", message: "該生效時間已有版本" } } });
    });
    renderPage();
    await screen.findByText("azure/gpt-5.4-mini");

    // header = 新增價格; priced row = 編輯價格; unpriced row = 設定價格
    fireEvent.click(screen.getByText("設定價格"));

    // default unit is per_1m → placeholders 0.15 / 0.60
    fireEvent.change(screen.getByPlaceholderText("0.15"), { target: { value: "0.30" } });
    fireEvent.change(screen.getByPlaceholderText("0.60"), { target: { value: "1.20" } });
    fireEvent.click(screen.getByText("新增"));

    await waitFor(() => expect(screen.getByText(/該生效時間已有版本/)).toBeInTheDocument());
    // per-1M 0.30 → per-1K 0.0003 (exact decimal shift, no float artifact)
    expect(posted.input_per_1k).toBe("0.0003");
    expect(posted.output_per_1k).toBe("0.0012");
    expect(posted.provider).toBe("azure");
    expect(posted.model).toBe("gpt-5.4-mini");
  });
});
