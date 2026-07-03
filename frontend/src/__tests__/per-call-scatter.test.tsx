import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { PerCallScatter, type CallPoint } from "@/components/per-call-scatter";

const RECORDS: CallPoint[] = [
  { id: "a", started_at: "2026-07-03T01:00:00Z", model: "azure/gpt-4o", total_tokens: 100, cost_usd: "0.05", outcome: "success", status_code: 200 },
  { id: "b", started_at: "2026-07-03T02:00:00Z", model: "azure/gpt-4o", total_tokens: 0, cost_usd: null, outcome: "upstream_error", status_code: 502 },
];

describe("<PerCallScatter /> (spec 056)", () => {
  it("shows cost/tokens toggle + per-call helper text", () => {
    render(<PerCallScatter records={RECORDS} />);
    expect(screen.getByRole("button", { name: "花費" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "tokens" })).toBeInTheDocument();
    expect(screen.getByText(/每個點是一次呼叫/)).toBeInTheDocument();
    expect(screen.getByText(/y=花費/)).toBeInTheDocument();
  });

  it("toggles the y metric to tokens", async () => {
    const user = userEvent.setup();
    render(<PerCallScatter records={RECORDS} />);
    await user.click(screen.getByRole("button", { name: "tokens" }));
    expect(screen.getByText(/y=tokens/)).toBeInTheDocument();
  });

  it("renders empty state when no plottable points", () => {
    render(<PerCallScatter records={[{ id: "x", started_at: "2026-07-03T01:00:00Z", cost_usd: null, total_tokens: null, outcome: "success" }]} />);
    // cost metric default + null cost + null tokens → no points
    expect(screen.getByText(/沒有可畫的呼叫/)).toBeInTheDocument();
  });
});
