import { afterEach, describe, expect, it, vi } from "vitest";

import { apiBlob, triggerDownload } from "@/lib/download";

describe("triggerDownload()", () => {
  afterEach(() => vi.restoreAllMocks());

  it("creates a blob URL, triggers click on a transient anchor, then revokes", () => {
    const url = "blob:mock";
    const createObjectURL = vi.fn().mockReturnValue(url);
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeObjectURL });

    // Spy on the real anchor click — let createElement create a real <a>
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    const blob = new Blob(["a,b,c"], { type: "text/csv" });
    triggerDownload("test.csv", blob);

    expect(createObjectURL).toHaveBeenCalledWith(blob);
    expect(clickSpy).toHaveBeenCalled();
    // The anchor is removed before revoke is queued (setTimeout)
    expect(document.querySelector("a[download='test.csv']")).toBeNull();
  });
});

describe("apiBlob()", () => {
  afterEach(() => vi.restoreAllMocks());

  it("returns a blob on 200", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("col1,col2\n1,2", { status: 200, headers: { "Content-Type": "text/csv" } }),
    );
    const blob = await apiBlob("/admin/usage.csv");
    expect(blob.size).toBeGreaterThan(0);
  });

  it("throws on non-2xx", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response("nope", { status: 500 }));
    await expect(apiBlob("/admin/usage.csv")).rejects.toThrow();
  });
});
