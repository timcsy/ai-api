import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AdminMemberCredentials } from "@/components/admin-member-credentials";
import { Toaster } from "@/components/ui/toaster";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const CREDS = [
  {
    id: "c1", name: "預設", token_prefix: "aiapi_aa", status: "active",
    allocations: [{ allocation_id: "a1", resource_model: "gpt-4o-mini", display_name: null, status: "active" }],
  },
];

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AdminMemberCredentials memberId="m1" />
      <Toaster />
    </QueryClientProvider>,
  );
}

describe("<AdminMemberCredentials />", () => {
  it("lists a member's keys and lets admin rename one", async () => {
    const calls: { url: string; method: string; body?: string }[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      const method = (init?.method ?? "GET").toUpperCase();
      calls.push({ url, method, body: init?.body as string | undefined });
      if (url.endsWith("/admin/members/m1/credentials")) return jsonResponse(200, CREDS);
      if (url.endsWith("/admin/credentials/c1") && method === "PATCH") return jsonResponse(200, { ...CREDS[0], name: "改好的名" });
      return jsonResponse(404, { error: {} });
    });
    const user = userEvent.setup();
    renderCard();
    await waitFor(() => expect(screen.getByText("預設")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "改名" }));
    const input = screen.getByDisplayValue("預設");
    await user.clear(input);
    await user.type(input, "改好的名");
    await user.click(screen.getByRole("button", { name: "儲存" }));

    await waitFor(() =>
      expect(calls.some((c) => c.url.endsWith("/admin/credentials/c1") && c.method === "PATCH")).toBe(true),
    );
  });
});
