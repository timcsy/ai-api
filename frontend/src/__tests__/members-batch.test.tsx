import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
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
  { id: "m1", email: "a@x.com", provider: "external", status: "active", is_admin: false, created_at: "2026-06-01T00:00:00Z", has_password: false },
  { id: "m2", email: "b@x.com", provider: "external", status: "active", is_admin: false, created_at: "2026-06-01T00:00:00Z", has_password: false },
];

function mockFetch(handler?: (url: string, init?: RequestInit) => Response | undefined) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    const method = (init?.method ?? "GET").toUpperCase();
    const custom = handler?.(url, init);
    if (custom) return custom;
    if (url.includes("/tags")) return json(200, []);
    if (url.endsWith("/admin/members") && method === "GET") return json(200, MEMBERS);
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

describe("<AdminMembersPage /> batch + safe delete", () => {
  beforeEach(() => vi.restoreAllMocks());

  // US1: single-delete confirm shows the cascade consequences
  it("single delete confirm explains cascade + key invalidation + usage retained", async () => {
    mockFetch();
    renderPage();
    const user = userEvent.setup();
    expect(await screen.findByText("a@x.com")).toBeInTheDocument();

    // open the first row's action menu, then click 刪除
    const firstRow = screen.getByText("a@x.com").closest("tr");
    expect(firstRow).not.toBeNull();
    const rowButtons = within(firstRow as HTMLElement).getAllByRole("button");
    await user.click(rowButtons[rowButtons.length - 1]!);
    await user.click(await screen.findByText("刪除"));

    // consequence text appears in the confirm dialog
    expect(await screen.findByText(/立即失效/)).toBeInTheDocument();
    expect(screen.getByText(/用量/)).toBeInTheDocument();
  });

  // US2: selecting members shows the batch bar + batch delete
  it("shows batch bar with selected count and runs batch delete", async () => {
    const calls: string[] = [];
    mockFetch((url, init) => {
      if (url.endsWith("/admin/members/bulk-delete")) {
        calls.push(url);
        return json(200, {
          deleted: 2, failed: 0,
          results: [
            { member_id: "m1", status: "deleted", reason: null },
            { member_id: "m2", status: "deleted", reason: null },
          ],
        });
      }
      void init;
      return undefined;
    });
    renderPage();
    const user = userEvent.setup();
    expect(await screen.findByText("a@x.com")).toBeInTheDocument();

    // select both rows via checkboxes
    const checkboxes = screen.getAllByRole("checkbox");
    // skip the header select-all (index 0); click the two row checkboxes
    await user.click(checkboxes[1]!);
    await user.click(checkboxes[2]!);

    expect(screen.getByText(/已選 2/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /批次刪除/ }));
    // confirm dialog
    await user.click(screen.getByRole("button", { name: /確認/ }));
    await waitFor(() => expect(calls.length).toBe(1));
  });

  // US3: batch create dialog renders the per-row summary
  it("batch create shows created/exists/invalid/duplicate summary with invite link", async () => {
    mockFetch((url) => {
      if (url.endsWith("/admin/members/bulk-create")) {
        return json(200, {
          created: 1, exists: 1, invalid: 1, duplicate: 0,
          results: [
            { email: "new@x.com", status: "created", invitation_url: "https://h/auth/invitation/tok" },
            { email: "old@x.com", status: "exists", invitation_url: null },
            { email: "bad", status: "invalid", invitation_url: null },
          ],
        });
      }
      return undefined;
    });
    renderPage();
    const user = userEvent.setup();
    expect(await screen.findByText("a@x.com")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /批次新增/ }));
    const textarea = await screen.findByPlaceholderText(/每行一個/);
    await user.type(textarea, "new@x.com\nold@x.com\nbad");
    await user.click(screen.getByRole("button", { name: /^建立$|送出|批次建立/ }));

    expect((await screen.findAllByText(/new@x.com/)).length).toBeGreaterThan(0);
    // the created row's invitation link
    expect(screen.getByRole("link", { name: /邀請連結/ })).toHaveAttribute(
      "href",
      "https://h/auth/invitation/tok",
    );
    expect(within(document.body).getAllByText(/old@x.com/).length).toBeGreaterThan(0);
  });
});
