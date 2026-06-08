import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { AdminModelDetailPage } from "@/routes/admin/model-detail";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const MODEL = {
  slug: "azure/gpt-4o", provider: "azure", display_name: "GPT-4o", family: "general",
  description: "", context_window: 128000, cost_tier: "medium", status: "active",
  modality_input: ["text", "image"], modality_output: ["text"],
  capabilities: ["chat", "vision", "function_calling", "prompt_caching"],
  recommended_for: [], tags: [], default_access: "open", allowed_tags: [], denied_tags: [],
  self_service_enabled: false, self_service_default_quota: null,
  price: { input_per_1k: "0.0025", output_per_1k: "0.01" },
  litellm_sync: {
    base_model_key: "azure/gpt-4o", imported_version: "1.85.1",
    field_sources: { context_window: "litellm", modality_input: "litellm", capabilities: "manual" },
    snapshot: {},
    raw: { mode: "chat", max_output_tokens: 16384, supports_vision: true },
  },
};

function renderDetail() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.endsWith("/admin/catalog/models")) return jsonResponse(200, [MODEL]);
    return jsonResponse(200, {}); // visibility etc. degrade
  });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/admin/model/azure/gpt-4o"]}>
        <Routes>
          <Route path="/admin/model/*" element={<AdminModelDetailPage />} />
        </Routes>
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("model detail — LiteLLM hub (Phase 24)", () => {
  it("shows source badges, the check-update entry, and the raw panel", async () => {
    renderDetail();
    await waitFor(() => expect(screen.getByText("GPT-4o")).toBeInTheDocument());
    // source badges: context/modality = LiteLLM, capabilities edited = 手動
    expect(screen.getAllByText("LiteLLM").length).toBeGreaterThan(0);
    expect(screen.getByText("手動")).toBeInTheDocument();
    // check-update entry on the detail page (single hub)
    expect(screen.getByRole("button", { name: "檢查 LiteLLM 更新" })).toBeInTheDocument();
    // read-only raw panel
    expect(screen.getByText(/LiteLLM 原始資訊/)).toBeInTheDocument();
  });
});
