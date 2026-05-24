import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/contexts/auth";
import { DashboardPage } from "@/routes/dashboard";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderDashboard(meStatus: number, meBody: unknown, allocations: unknown) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.endsWith("/me")) return jsonResponse(meStatus, meBody);
      if (url.endsWith("/me/allocations")) {
        if (Array.isArray(allocations)) return jsonResponse(200, allocations);
        return jsonResponse(500, { error: { code: "boom", message: "DB exploded" } });
      }
      return jsonResponse(404, { error: {} });
    });
  return {
    fetchMock,
    ...render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/dashboard"]}>
          <AuthProvider queryClient={qc}>
            <Routes>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/dashboard/allocations/:id" element={<div>detail</div>} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
}

describe("<DashboardPage />", () => {
  it("renders empty state when there are no allocations", async () => {
    renderDashboard(200, { id: "m", email: "alice@x.com", provider: "local_password" }, []);
    await waitFor(() => expect(screen.getByText(/尚未獲得任何分配/)).toBeInTheDocument());
  });

  it("renders allocation cards and hides revoked by default", async () => {
    renderDashboard(
      200,
      { id: "m", email: "alice@x.com", provider: "local_password" },
      [
        {
          id: "a1",
          member_id: "m",
          subject_snapshot: "alice@x.com",
          resource_model: "gpt-4o-mini",
          status: "active",
          created_at: "2026-05-24T00:00:00+00:00",
          revoked_at: null,
          token_prefix: "aiapi_xx",
        },
        {
          id: "a2",
          member_id: "m",
          subject_snapshot: "alice@x.com",
          resource_model: "dall-e-3",
          status: "revoked",
          created_at: "2026-04-01T00:00:00+00:00",
          revoked_at: "2026-05-01T00:00:00+00:00",
          token_prefix: "aiapi_yy",
        },
      ],
    );
    await waitFor(() => expect(screen.getByText("gpt-4o-mini")).toBeInTheDocument());
    expect(screen.queryByText("dall-e-3")).not.toBeInTheDocument();

    // toggle includeRevoked → revoked shows
    await userEvent.click(screen.getByRole("switch", { name: /含已撤回/ }));
    await waitFor(() => expect(screen.getByText("dall-e-3")).toBeInTheDocument());
  });

  it("shows error block with retry on /me/allocations 500", async () => {
    renderDashboard(200, { id: "m", email: "alice@x.com" }, null);
    await waitFor(() => expect(screen.getByText(/無法載入分配/)).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "重試" })).toBeInTheDocument();
  });
});
