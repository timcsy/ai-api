import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AdminRoute } from "@/components/admin-route";
import { AuthProvider } from "@/contexts/auth";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderRoute(meBody: unknown, meStatus = 200) {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(jsonResponse(meStatus, meBody));
  return render(
    <MemoryRouter initialEntries={["/admin/members"]}>
      <AuthProvider>
        <Routes>
          <Route element={<AdminRoute />}>
            <Route path="/admin/members" element={<div data-testid="admin-page">admin</div>} />
          </Route>
          <Route path="/dashboard" element={<div data-testid="home">home</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("<AdminRoute />", () => {
  it("shows loading state while auth hydrates", () => {
    vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise(() => {}));
    render(
      <MemoryRouter initialEntries={["/admin/members"]}>
        <AuthProvider>
          <Routes>
            <Route element={<AdminRoute />}>
              <Route path="/admin/members" element={<div>x</div>} />
            </Route>
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText(/載入中/)).toBeInTheDocument();
  });

  it("denies non-admin members with inline 無權限 page", async () => {
    renderRoute({ id: "m1", email: "bob@x.com", is_admin: false });
    await waitFor(() => expect(screen.getByText("無權限查看")).toBeInTheDocument());
    expect(screen.queryByTestId("admin-page")).not.toBeInTheDocument();
  });

  it("renders children when member.is_admin === true", async () => {
    renderRoute({ id: "m1", email: "alice@x.com", is_admin: true });
    await waitFor(() => expect(screen.getByTestId("admin-page")).toBeInTheDocument());
  });

  it("denies even authenticated members when is_admin missing/undefined", async () => {
    renderRoute({ id: "m1", email: "bob@x.com" }); // no is_admin
    await waitFor(() => expect(screen.getByText("無權限查看")).toBeInTheDocument());
  });
});
