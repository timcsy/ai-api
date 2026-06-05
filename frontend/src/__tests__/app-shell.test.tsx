import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/app-shell";
import { AuthProvider } from "@/contexts/auth";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderShell(initialEntry: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialEntry]}>
          <AuthProvider queryClient={queryClient}>
            <Routes>
              <Route element={<AppShell />}>
                <Route path="/dashboard" element={<div data-testid="dash">dash</div>} />
                <Route path="/keys" element={<div data-testid="keys">keys</div>} />
                <Route path="/allocations" element={<div data-testid="allocs">allocs</div>} />
                <Route path="/usage" element={<div data-testid="usage">usage</div>} />
                <Route path="/catalog" element={<div data-testid="cat">cat</div>} />
              </Route>
              <Route path="/login" element={<div data-testid="login">login</div>} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
}

describe("<AppShell />", () => {
  it("renders header with member email after auth hydration", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse(200, { id: "m1", email: "alice@x.com" }),
    );
    renderShell("/dashboard");
    await waitFor(() => expect(screen.getByTestId("dash")).toBeInTheDocument());
    expect(screen.getByTestId("member-email")).toHaveTextContent("alice@x.com");
  });

  it("nav links route between Dashboard and Catalog", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse(200, { id: "m1", email: "alice@x.com" }),
    );
    renderShell("/dashboard");
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByTestId("dash")).toBeInTheDocument());

    await user.click(screen.getByText("模型目錄"));
    expect(screen.getByTestId("cat")).toBeInTheDocument();
  });

  it("exposes 金鑰 / 分配 / 用量 member pages and routes to them", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse(200, { id: "m1", email: "alice@x.com" }),
    );
    renderShell("/dashboard");
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByTestId("dash")).toBeInTheDocument());

    await user.click(screen.getByText("金鑰"));
    expect(screen.getByTestId("keys")).toBeInTheDocument();
    await user.click(screen.getByText("分配"));
    expect(screen.getByTestId("allocs")).toBeInTheDocument();
    await user.click(screen.getByText("用量"));
    expect(screen.getByTestId("usage")).toBeInTheDocument();
  });

  it("logout clears queryClient cache and tracks unauthenticated state", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(200, { id: "m1", email: "alice@x.com" })) // /me
      .mockResolvedValueOnce(new Response(null, { status: 204 })); // /auth/logout

    const { queryClient } = renderShell("/dashboard");
    queryClient.setQueryData(["dummy"], { stash: "ME" });

    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByTestId("dash")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "登出" }));
    await waitFor(() => expect(queryClient.getQueryData(["dummy"])).toBeUndefined());

    const logoutCall = fetchMock.mock.calls[1];
    expect(logoutCall?.[0]).toBe("/auth/logout");
  });
});
