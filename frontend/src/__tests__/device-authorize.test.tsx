import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { DeviceAuthorizePage } from "@/routes/device-authorize";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderPage(code: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/device?code=${code}`]}>
        <Routes>
          <Route path="/device" element={<DeviceAuthorizePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("<DeviceAuthorizePage />", () => {
  it("shows the device request summary and the member's allocations to pick", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.includes("/me/device/ABCD-EFGH")) {
        return jsonResponse(200, {
          user_code: "ABCD-EFGH",
          device_label: "Codex on host-x",
          status: "pending",
          created_at: "2026-06-05T00:00:00Z",
          expires_at: "2026-06-05T00:10:00Z",
        });
      }
      if (url.endsWith("/me/allocations")) {
        return jsonResponse(200, [
          { id: "a1", resource_model: "gpt-4o-mini", display_name: "GPT-4o mini", status: "active" },
        ]);
      }
      return jsonResponse(404, { error: {} });
    });

    renderPage("ABCD-EFGH");

    await waitFor(() => expect(screen.getByText("Codex on host-x")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "授權這台裝置" })).toBeInTheDocument();
    expect(screen.getByText("這台裝置可用哪些 model（可多選）")).toBeInTheDocument();
  });

  it("surfaces an error for an unknown / expired code", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(404, { error: { code: "not_found", message: "gone" } }),
    );
    renderPage("ZZZZ-ZZZZ");
    await waitFor(() =>
      expect(screen.getByText(/找不到或已過期的代碼/)).toBeInTheDocument(),
    );
  });
});
