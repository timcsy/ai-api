import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { AdminOAuthPage } from "@/routes/admin/oauth";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function setup(handler?: (url: string, init?: RequestInit) => Response | undefined) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    const custom = handler?.(url, init);
    if (custom) return custom;
    if (url.endsWith("/admin/oauth/config") && (init?.method ?? "GET") === "GET") {
      return json(200, {
        redirect_allowlist: "https://a.test/",
        prefixes: ["https://a.test/"],
        updated_at: null,
        updated_by: null,
      });
    }
    return json(404, { error: {} });
  });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AdminOAuthPage />
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("<AdminOAuthPage />", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("loads the allowlist and saves an edit", async () => {
    let body: unknown = null;
    setup((url, init) => {
      if (url.endsWith("/admin/oauth/config") && init?.method === "PUT") {
        body = JSON.parse((init.body as string) ?? "{}");
        return json(200, {
          redirect_allowlist: "https://a.test/\nhttps://b.test/",
          prefixes: ["https://a.test/", "https://b.test/"],
          updated_at: "2026-08-25T00:00:00Z",
          updated_by: "admin1",
        });
      }
      return undefined;
    });
    const user = userEvent.setup();
    const box = (await screen.findByRole("textbox")) as HTMLTextAreaElement;
    await waitFor(() => expect(box.value).toContain("https://a.test/"));

    await user.type(box, "\nhttps://b.test/");
    await user.click(screen.getByRole("button", { name: "儲存" }));
    await waitFor(() => expect(body).not.toBeNull());
    expect((body as { redirect_allowlist: string }).redirect_allowlist).toContain("https://b.test/");
  });
});
