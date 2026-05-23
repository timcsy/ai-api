import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, UNAUTHORIZED_EVENT, api } from "@/lib/api-client";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api()", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("returns parsed body on 200", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse(200, { id: "abc" }),
    );
    const result = await api<{ id: string }>("/me");
    expect(result).toEqual({ id: "abc" });
  });

  it("returns undefined on 204 No Content", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(null, { status: 204 }),
    );
    const result = await api<undefined>("/auth/logout", { method: "POST" });
    expect(result).toBeUndefined();
  });

  it("throws ApiError on 401 and dispatches the unauthorized event", async () => {
    const listener = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, listener);
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse(401, { error: { code: "unauthorized", message: "session required" } }),
    );

    await expect(api("/me")).rejects.toBeInstanceOf(ApiError);
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener(UNAUTHORIZED_EVENT, listener);
  });

  it("throws ApiError with parsed code+message on 5xx", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse(500, { error: { code: "upstream_error", message: "boom" } }),
    );
    try {
      await api("/v1/chat/completions", { method: "POST", body: "{}" });
      throw new Error("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      const err = e as ApiError;
      expect(err.status).toBe(500);
      expect(err.code).toBe("upstream_error");
      expect(err.message).toBe("boom");
    }
  });

  it("sends credentials include + JSON content-type by default", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(200, {}));
    await api("/me");
    const init = spy.mock.calls[0]?.[1] as RequestInit;
    expect(init.credentials).toBe("include");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });
});
