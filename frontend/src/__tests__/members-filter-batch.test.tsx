import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { AdminMembersPage } from "@/routes/admin/members";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const MEMBERS = [
  { id: "m1", email: "alice@x.com", provider: "external", status: "active", is_admin: false, created_at: "2026-06-01T00:00:00Z", has_password: false, tags: ["class-a"] },
  { id: "m2", email: "bob@x.com", provider: "local_password", status: "active", is_admin: false, created_at: "2026-06-01T00:00:00Z", has_password: true, tags: ["class-b"] },
];

function mockFetch(handler?: (url: string, init?: RequestInit) => Response | undefined) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    const method = (init?.method ?? "GET").toUpperCase();
    const custom = handler?.(url, init);
    if (custom) return custom;
    if (url.endsWith("/admin/members") && method === "GET") return json(200, MEMBERS);
    if (url.includes("/tags")) return json(200, []);
    return json(200, {});
  });
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AdminMembersPage />
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("<AdminMembersPage /> filter + batch ops", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("search box narrows the visible rows", async () => {
    mockFetch();
    renderPage();
    const user = userEvent.setup();
    expect(await screen.findByText("alice@x.com")).toBeInTheDocument();
    expect(screen.getByText("bob@x.com")).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText(/搜尋帳號/), "alice");
    await waitFor(() => expect(screen.queryByText("bob@x.com")).not.toBeInTheDocument());
    expect(screen.getByText("alice@x.com")).toBeInTheDocument();
  });

  it("batch disable posts selected ids to bulk-status", async () => {
    let body: unknown = null;
    mockFetch((url, init) => {
      if (url.endsWith("/admin/members/bulk-status")) {
        body = JSON.parse((init?.body as string) ?? "{}");
        return json(200, { changed: 2, failed: 0, results: [] });
      }
      return undefined;
    });
    renderPage();
    const user = userEvent.setup();
    expect(await screen.findByText("alice@x.com")).toBeInTheDocument();

    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]!); // header select-all (all filtered)
    expect(screen.getByText(/已選 2/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "批次停用" }));
    await waitFor(() => expect(body).not.toBeNull());
    expect((body as { status: string }).status).toBe("disabled");
    expect((body as { member_ids: string[] }).member_ids.sort()).toEqual(["m1", "m2"]);
  });

  it("batch tags dialog posts add tags", async () => {
    let body: unknown = null;
    mockFetch((url, init) => {
      if (url.endsWith("/admin/members/bulk-tags")) {
        body = JSON.parse((init?.body as string) ?? "{}");
        return json(200, { changed: 1, failed: 0, results: [] });
      }
      return undefined;
    });
    renderPage();
    const user = userEvent.setup();
    expect(await screen.findByText("alice@x.com")).toBeInTheDocument();

    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[1]!); // first row
    await user.click(screen.getByRole("button", { name: "批次標籤" }));

    await user.type(await screen.findByPlaceholderText(/以空白或逗號分隔/), "grade-3");
    await user.click(screen.getByRole("button", { name: "套用" }));
    await waitFor(() => expect(body).not.toBeNull());
    expect((body as { add: string[] }).add).toEqual(["grade-3"]);
  });
});
