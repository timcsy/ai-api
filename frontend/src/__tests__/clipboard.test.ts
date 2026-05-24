import { afterEach, describe, expect, it, vi } from "vitest";

import { copyToClipboard } from "@/lib/clipboard";

describe("copyToClipboard()", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns true and calls writeText when clipboard API is available", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const result = await copyToClipboard("hello");
    expect(result).toBe(true);
    expect(writeText).toHaveBeenCalledWith("hello");
  });

  it("returns false when writeText rejects", async () => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
    });
    const result = await copyToClipboard("hello");
    expect(result).toBe(false);
  });

  it("returns false when clipboard API is missing", async () => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: undefined,
    });
    const result = await copyToClipboard("hello");
    expect(result).toBe(false);
  });
});
