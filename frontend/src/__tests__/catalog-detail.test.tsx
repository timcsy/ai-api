import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/contexts/auth";
import { CatalogDetailPage } from "@/routes/catalog-detail";
import { Toaster } from "@/components/ui/toaster";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const DALLE_DETAIL = {
  slug: "azure/dall-e-3",
  display_name: "DALL·E 3",
  family: "dall-e",
  description: "image gen",
  modality_input: ["text"],
  modality_output: ["image"],
  capabilities: [],
  context_window: 4000,
  cost_tier: "high",
  recommended_for: ["image-gen"],
  tags: [],
  official_doc_url: null,
  status: "active",
  deprecation_note: null,
  example_request: {
    curl: "curl -X POST $BASE/v1/images/generations -H 'Authorization: Bearer $TOKEN'",
    body: { model: "dall-e-3", prompt: "a cat" },
  },
};

const DEPRECATED_DETAIL = {
  ...DALLE_DETAIL,
  slug: "azure/whisper-old",
  display_name: "Old Whisper",
  status: "deprecated",
  deprecation_note: "請改用 whisper-1",
};

function renderDetail(slug: string, body: unknown, status = 200) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.endsWith("/me")) return jsonResponse(200, { id: "m", email: "a@x.com" });
    if (url.includes("/catalog/models/")) return jsonResponse(status, body);
    return jsonResponse(404, { error: {} });
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/catalog/${slug}`]}>
        <AuthProvider queryClient={qc}>
          <Routes>
            <Route path="/catalog/*" element={<CatalogDetailPage />} />
          </Routes>
          <Toaster />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("<CatalogDetailPage />", () => {
  it("renders description + capabilities + tabs", async () => {
    renderDetail("azure/dall-e-3", DALLE_DETAIL);
    await waitFor(() => expect(screen.getByText("DALL·E 3")).toBeInTheDocument());
    expect(screen.getByText("image gen")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "curl" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "JSON body" })).toBeInTheDocument();
  });

  it("clicking 複製 curl writes to clipboard and shows success toast", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    renderDetail("azure/dall-e-3", DALLE_DETAIL);
    await waitFor(() => expect(screen.getByText("DALL·E 3")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "複製 curl" }));
    expect(writeText).toHaveBeenCalledWith(DALLE_DETAIL.example_request.curl);
    await waitFor(() => expect(screen.getByText("已複製到剪貼簿")).toBeInTheDocument());
  });

  it("shows fallback toast when clipboard API unavailable", async () => {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined });

    renderDetail("azure/dall-e-3", DALLE_DETAIL);
    await waitFor(() => expect(screen.getByText("DALL·E 3")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "複製 curl" }));
    await waitFor(() => expect(screen.getByText("複製失敗")).toBeInTheDocument());
  });

  it("shows deprecation banner for deprecated models", async () => {
    renderDetail("azure/whisper-old", DEPRECATED_DETAIL);
    await waitFor(() => expect(screen.getByText("此模型已停用")).toBeInTheDocument());
    expect(screen.getByText("請改用 whisper-1")).toBeInTheDocument();
  });

  it("shows 404 page when slug not found", async () => {
    renderDetail("azure/nope", { error: { code: "not_found" } }, 404);
    await waitFor(() => expect(screen.getByText(/找不到模型/)).toBeInTheDocument());
  });
});
