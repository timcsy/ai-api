import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DeviceCredentialsCard } from "@/components/device-credentials-card";
import { Toaster } from "@/components/ui/toaster";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const CREDS = [
  {
    id: "c1",
    name: "預設",
    token_prefix: "aiapi_aa",
    created_at: "2026-06-01T00:00:00+00:00",
    last_used_at: "2026-06-02T03:00:00+00:00",
    status: "active",
  },
  {
    id: "c2",
    name: "我的筆電",
    token_prefix: "aiapi_bb",
    created_at: "2026-06-03T00:00:00+00:00",
    last_used_at: null,
    status: "active",
  },
];

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <DeviceCredentialsCard allocationId="a1" basePath="/me/allocations" scope="me" allowAdd />
      <Toaster />
    </QueryClientProvider>,
  );
}

describe("<DeviceCredentialsCard />", () => {
  it("lists device credentials without leaking any plaintext token", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(200, CREDS));
    renderCard();

    await waitFor(() => expect(screen.getByText("我的筆電")).toBeInTheDocument());
    expect(screen.getByText("預設")).toBeInTheDocument();
    expect(screen.getByText("aiapi_aa…")).toBeInTheDocument();
    // The list payload carries no plaintext token, so nothing token-like renders.
    expect(screen.queryByText(/aiapi_aa[a-z0-9]{6,}/i)).not.toBeInTheDocument();
  });

  it("adds a device and reveals the one-time token with a copy control", async () => {
    const created = {
      id: "c3",
      name: "桌機",
      token: "aiapi_secretsecretsecret",
      token_prefix: "aiapi_cc",
    };
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.endsWith("/me/allocations/a1/credentials") && method === "POST") {
        return jsonResponse(201, created);
      }
      return jsonResponse(200, CREDS);
    });

    const user = userEvent.setup();
    renderCard();
    await waitFor(() => expect(screen.getByText("預設")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "新增裝置" }));
    await user.type(screen.getByLabelText("裝置名"), "桌機");
    await user.click(screen.getByRole("button", { name: "新增" }));

    // The reveal dialog shows the plaintext token exactly once.
    await waitFor(() =>
      expect(screen.getByText("aiapi_secretsecretsecret")).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "複製" })).toBeInTheDocument();
  });
});
