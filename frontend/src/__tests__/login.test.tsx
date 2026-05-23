import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/contexts/auth";
import { LoginPage, sanitizeNext } from "@/routes/login";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderLogin(initialEntry = "/login") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div data-testid="home">home</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("sanitizeNext()", () => {
  it("returns '/' for null / empty", () => {
    expect(sanitizeNext(null)).toBe("/");
    expect(sanitizeNext("")).toBe("/");
  });
  it("returns '/' for protocol-relative URLs (//evil)", () => {
    expect(sanitizeNext("//evil.com/x")).toBe("/");
  });
  it("returns '/' for absolute URLs", () => {
    expect(sanitizeNext("http://evil.com")).toBe("/");
    expect(sanitizeNext("https://evil.com")).toBe("/");
  });
  it("returns '/' for backslash-containing paths", () => {
    expect(sanitizeNext("/\\evil")).toBe("/");
  });
  it("returns the input for legitimate relative paths", () => {
    expect(sanitizeNext("/admin/usage")).toBe("/admin/usage");
    expect(sanitizeNext("/?q=1")).toBe("/?q=1");
  });
});

describe("<LoginPage />", () => {
  it("submits credentials and navigates to next on success", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(401, { error: {} })) // initial /me
      .mockResolvedValueOnce(jsonResponse(200, {})) // POST /auth/local/login
      .mockResolvedValueOnce(
        jsonResponse(200, { id: "m1", email: "alice@x.com" }), // refresh /me
      );

    renderLogin("/login");
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Email"), "alice@x.com");
    await user.type(screen.getByLabelText("密碼"), "pw");
    await user.click(screen.getByRole("button", { name: "登入" }));

    await waitFor(() => expect(screen.getByTestId("home")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("shows backend error message when login fails", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(401, { error: {} })) // initial /me
      .mockResolvedValueOnce(
        jsonResponse(401, {
          error: { code: "invalid_credentials", message: "auth failed" },
        }),
      );

    renderLogin("/login");
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Email"), "bad@x.com");
    await user.type(screen.getByLabelText("密碼"), "wrong");
    await user.click(screen.getByRole("button", { name: "登入" }));

    await waitFor(() =>
      expect(screen.getByTestId("login-error")).toHaveTextContent("auth failed"),
    );
  });
});
