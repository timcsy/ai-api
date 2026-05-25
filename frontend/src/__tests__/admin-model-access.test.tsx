import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { AdminModelAccessPage } from "@/routes/admin/model-access";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("<AdminModelAccessPage />", () => {
  it("renders model picker and waits for selection before showing policy form", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.includes("/catalog/models")) {
        return jsonResponse(200, [
          { slug: "azure/gpt-4o", display_name: "GPT-4o", provider: "azure" },
        ]);
      }
      if (url.endsWith("/admin/tags")) return jsonResponse(200, []);
      return jsonResponse(404, { error: {} });
    });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <AdminModelAccessPage />
          <Toaster />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByText("Model 存取規則")).toBeInTheDocument();
    expect(screen.getByText("選擇 Model")).toBeInTheDocument();
    // Policy form not visible until selection
    expect(screen.queryByText("存取政策")).not.toBeInTheDocument();
  });
});
