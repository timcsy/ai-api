import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { OAuthAuthorizePage } from "@/routes/oauth-authorize";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const PARAMS =
  "?client_name=My%20Transcriber&redirect_uri=https://app.test/callback" +
  "&code_challenge=abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG&code_challenge_method=S256&state=xyz";

function setup(handler?: (url: string, init?: RequestInit) => Response | undefined) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    const custom = handler?.(url, init);
    if (custom) return custom;
    if (url.endsWith("/me/oauth/consent")) {
      return json(200, {
        id: "auth1",
        client_name: "My Transcriber",
        redirect_uri: "https://app.test/callback",
        scope: null,
        allocations: [{ id: "al1", resource_model: "azure/gpt-4o-mini", display_name: null }],
      });
    }
    return json(404, { error: {} });
  });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/oauth/authorize${PARAMS}`]}>
        <OAuthAuthorizePage />
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("<OAuthAuthorizePage />", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // jsdom throws on real navigation; stub a settable href.
    Object.defineProperty(window, "location", { value: { href: "" }, writable: true });
  });
  afterEach(() => vi.restoreAllMocks());

  it("shows the app name + allocations and approve posts the picked ids", async () => {
    let body: unknown = null;
    setup((url, init) => {
      if (url.endsWith("/me/oauth/auth1/approve")) {
        body = JSON.parse((init?.body as string) ?? "{}");
        return json(200, { redirect_uri: "https://app.test/callback", code: "CODE123", state: "xyz" });
      }
      return undefined;
    });
    const user = userEvent.setup();
    expect(await screen.findByText(/My Transcriber/)).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "核准" }));
    await waitFor(() => expect(body).not.toBeNull());
    expect((body as { allocation_ids: string[] }).allocation_ids).toEqual(["al1"]);
    // redirected back to the app with the code
    await waitFor(() => expect(window.location.href).toContain("code=CODE123"));
    expect(window.location.href).toContain("state=xyz");
  });

  it("shows an error when redirect_uri is rejected", async () => {
    setup((url) => {
      if (url.endsWith("/me/oauth/consent")) {
        return json(400, { error: { code: "redirect_uri_not_allowed", message: "no" } });
      }
      return undefined;
    });
    expect(await screen.findByText(/返回網址不在允許清單/)).toBeInTheDocument();
  });
});
