// Price unit conversion + display helpers.
// Storage/billing unit is per-1K tokens; vendors quote per-1M, so the UI
// commonly displays/enters per-1M. These do EXACT decimal-point shifts to
// avoid floating-point artifacts on money values.

export type PriceUnit = "per_1k" | "per_1m";

export const UNIT_LABEL: Record<PriceUnit, string> = { per_1k: "1K", per_1m: "1M" };

/** per-1M → per-1K (÷1000): "0.15" → "0.00015", "2.5" → "0.0025". */
export function per1mToPer1k(value: string): string {
  const v = value.trim();
  if (!/^-?\d*\.?\d+$/.test(v)) return value;
  const neg = v.startsWith("-");
  const [intPart, fracPart = ""] = v.replace("-", "").split(".");
  const digits = intPart + fracPart;
  const pointFromRight = fracPart.length + 3;
  const padded = digits.padStart(pointFromRight + 1, "0");
  const cut = padded.length - pointFromRight;
  const out = `${padded.slice(0, cut)}.${padded.slice(cut)}`
    .replace(/^0+(?=\d)/, "")
    .replace(/(\.\d*?)0+$/, "$1")
    .replace(/\.$/, "");
  return (neg ? "-" : "") + out;
}

/** per-1K → per-1M (×1000): "0.0003" → "0.3", "0.00120000" → "1.2". */
export function per1kToPer1m(value: string): string {
  const v = value.trim();
  if (!/^-?\d*\.?\d+$/.test(v)) return value;
  const neg = v.startsWith("-");
  const [intPart, fracRaw = ""] = v.replace("-", "").split(".");
  const frac = fracRaw.padEnd(3, "0");
  const moved = (intPart + frac.slice(0, 3)).replace(/^0+(?=\d)/, "");
  const rest = frac.slice(3).replace(/0+$/, "");
  const out = rest ? `${moved}.${rest}` : moved;
  return (neg ? "-" : "") + (out || "0");
}

/** Display a stored per-1K price string in the chosen unit. */
export function displayPrice(per1k: string, unit: PriceUnit): string {
  return unit === "per_1m" ? per1kToPer1m(per1k) : per1k;
}
