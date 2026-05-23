import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ProtectedRoute } from "@/components/protected-route";
import { AuthProvider } from "@/contexts/auth";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderWithRoute(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AuthProvider>
        <Routes>
          <Route
            path="/protected"
            element={
              <ProtectedRoute>
                <div>secret</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div data-testid="login-redirected">login</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("<ProtectedRoute />", () => {
  it("renders loading state while AuthProvider hydrates", () => {
    vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise(() => {}));
    renderWithRoute("/protected");
    expect(screen.getByText(/載入中/)).toBeInTheDocument();
  });

  it("redirects to /login when unauthenticated", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse(401, { error: {} }),
    );
    renderWithRoute("/protected");
    await waitFor(() => expect(screen.getByTestId("login-redirected")).toBeInTheDocument());
  });

  it("renders children when authenticated", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse(200, { id: "m1", email: "a@x.com" }),
    );
    renderWithRoute("/protected");
    await waitFor(() => expect(screen.getByText("secret")).toBeInTheDocument());
  });
});
