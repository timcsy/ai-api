import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "@/contexts/auth";
import { UNAUTHORIZED_EVENT } from "@/lib/api-client";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <AuthProvider>{children}</AuthProvider>
);

describe("AuthContext", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("hydrates to authenticated when /me returns 200", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse(200, { id: "m1", email: "a@x.com" }),
    );
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe("authenticated"));
    expect(result.current.member?.email).toBe("a@x.com");
  });

  it("hydrates to unauthenticated when /me returns 401", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse(401, { error: { code: "unauthorized", message: "no" } }),
    );
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe("unauthenticated"));
    expect(result.current.member).toBeNull();
  });

  it("login() refreshes member from /me", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      // initial /me -> 401
      .mockResolvedValueOnce(jsonResponse(401, { error: {} }))
      // POST /auth/local/login -> 200
      .mockResolvedValueOnce(jsonResponse(200, {}))
      // refresh /me -> 200
      .mockResolvedValueOnce(jsonResponse(200, { id: "m2", email: "alice@x.com" }));

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe("unauthenticated"));

    await act(async () => {
      await result.current.login("alice@x.com", "pw");
    });
    expect(result.current.status).toBe("authenticated");
    expect(result.current.member?.email).toBe("alice@x.com");

    const loginCall = fetchMock.mock.calls[1];
    expect(loginCall?.[0]).toBe("/auth/local/login");
  });

  it("api:unauthorized event resets state", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse(200, { id: "m1", email: "a@x.com" }),
    );
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe("authenticated"));

    act(() => {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    });
    expect(result.current.status).toBe("unauthenticated");
    expect(result.current.member).toBeNull();
  });

  it("logout() POSTs /auth/logout and clears state", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(200, { id: "m1", email: "a@x.com" }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBe("authenticated"));

    await act(async () => {
      await result.current.logout();
    });
    expect(result.current.status).toBe("unauthenticated");
    const logoutCall = fetchMock.mock.calls[1];
    expect(logoutCall?.[0]).toBe("/auth/logout");
    expect((logoutCall?.[1] as RequestInit).method).toBe("POST");
  });
});
