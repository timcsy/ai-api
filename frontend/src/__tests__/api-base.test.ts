import { describe, expect, it } from "vitest";

import { apiBaseUrl } from "@/lib/api-base";

describe("apiBaseUrl", () => {
  it("returns the browser origin + /v1 (single source of truth)", () => {
    expect(apiBaseUrl()).toBe(`${window.location.origin}/v1`);
  });

  it("ends with /v1", () => {
    expect(apiBaseUrl().endsWith("/v1")).toBe(true);
  });
});
