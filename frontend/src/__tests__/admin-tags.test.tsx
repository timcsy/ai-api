import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { AdminTagsPage } from "@/routes/admin/tags";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("<AdminTagsPage />", () => {
  it("shows empty state when no tags exist", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(200, []));
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <AdminTagsPage />
          <Toaster />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() =>
      expect(screen.getByText(/目前沒有任何標籤/)).toBeInTheDocument(),
    );
  });

  it("renders tag rows with member counts", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(200, [
        { tag: "eng", member_count: 5 },
        { tag: "pm", member_count: 2 },
      ]),
    );
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <AdminTagsPage />
          <Toaster />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText("eng")).toBeInTheDocument();
    expect(screen.getByText("pm")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });
});
