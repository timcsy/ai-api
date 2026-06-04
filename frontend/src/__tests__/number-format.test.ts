import { describe, expect, it } from "vitest";

import { fmtCompact } from "@/lib/number-format";

describe("fmtCompact (K/M/B chart axis)", () => {
  it("abbreviates large token counts", () => {
    expect(fmtCompact(0)).toBe("0");
    expect(fmtCompact(950)).toBe("950");
    expect(fmtCompact(1500)).toBe("1.5K");
    expect(fmtCompact(2_000_000)).toBe("2M");
    expect(fmtCompact(2_500_000)).toBe("2.5M");
    expect(fmtCompact(1_200_000_000)).toBe("1.2B");
  });
});
