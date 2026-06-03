import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/app-shell";
import { AuthProvider } from "@/contexts/auth";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Simulate a viewport width + matching matchMedia so useIsMobile() resolves. */
function setViewport(width: number) {
  Object.defineProperty(window, "innerWidth", { writable: true, configurable: true, value: width });
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: width < 768,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

function renderShell(isAdmin: boolean) {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    jsonResponse(200, { id: "m1", email: "admin@example.com", is_admin: isAdmin }),
  );
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AuthProvider queryClient={queryClient}>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/dashboard" element={<div data-testid="dash">dash</div>} />
              <Route path="/catalog" element={<div data-testid="cat">cat</div>} />
            </Route>
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const SUBNAV = ["首頁", "Model", "成員", "Tag", "Provider 憑證", "存取", "通知", "觀測"];

afterEach(() => {
  vi.restoreAllMocks();
});

describe("mobile navigation (Phase 16 US1)", () => {
  it("shows a hamburger button on phones and the drawer lists every destination", async () => {
    setViewport(375);
    renderShell(true);
    await waitFor(() => expect(screen.getByTestId("dash")).toBeInTheDocument());

    // hamburger present on mobile (accessible name)
    const hamburger = await screen.findByRole("button", { name: /選單/ });
    const user = userEvent.setup();
    await user.click(hamburger);

    // drawer (dialog) contains all main destinations + admin sub-nav + logout
    const dialog = await screen.findByRole("dialog");
    const drawer = within(dialog);
    expect(drawer.getByText("我的儀表板")).toBeInTheDocument();
    expect(drawer.getByText("模型目錄")).toBeInTheDocument();
    expect(drawer.getByText("管理員")).toBeInTheDocument();
    for (const label of SUBNAV) {
      expect(drawer.getByText(label)).toBeInTheDocument();
    }
    expect(drawer.getByRole("button", { name: "登出" })).toBeInTheDocument();
  });

  it("on desktop shows no hamburger and keeps the inline nav", async () => {
    setViewport(1280);
    renderShell(true);
    await waitFor(() => expect(screen.getByTestId("dash")).toBeInTheDocument());

    expect(screen.queryByRole("button", { name: /選單/ })).not.toBeInTheDocument();
    // inline nav still routes
    expect(screen.getByText("模型目錄")).toBeInTheDocument();
  });
});
