import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiUsageExample } from "@/components/api-usage-example";

describe("<ApiUsageExample />", () => {
  it("shows only chat tabs when responses unsupported", () => {
    render(<ApiUsageExample model="azure/gpt-4o" />);
    expect(screen.getByText("curl")).toBeInTheDocument();
    expect(screen.queryByText(/Responses \(curl\)/)).not.toBeInTheDocument();
  });

  it("adds Responses tabs when supported (Codex setup moved to the install card)", () => {
    render(<ApiUsageExample model="azure/gpt-5.4" supportsResponses />);
    expect(screen.getByText("Responses (curl)")).toBeInTheDocument();
    expect(screen.getByText("Responses (Py)")).toBeInTheDocument();
    // Phase 20: the per-model Codex config tab was removed; no Codex tab remains.
    expect(screen.queryByRole("tab", { name: "Codex" })).not.toBeInTheDocument();
  });
});
