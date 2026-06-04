// Compact number formatting (K / M / B) for chart axes and tight labels, so a
// 2,000,000 token axis reads "2M" instead of overflowing / getting clipped.
const compact = new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: 1,
});

/** e.g. 0 → "0", 1500 → "1.5K", 2_000_000 → "2M", 1_200_000_000 → "1.2B". */
export function fmtCompact(n: number): string {
  return compact.format(n);
}
