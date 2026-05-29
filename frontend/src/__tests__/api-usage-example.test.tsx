import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ApiUsageExample } from "@/components/api-usage-example";

describe("<ApiUsageExample />", () => {
  it("shows only chat tabs when responses unsupported", () => {
    render(<ApiUsageExample model="azure/gpt-4o" />);
    expect(screen.getByText("curl")).toBeInTheDocument();
    expect(screen.queryByText("Codex")).not.toBeInTheDocument();
    expect(screen.queryByText(/Responses \(curl\)/)).not.toBeInTheDocument();
  });

  it("adds Responses + Codex tabs when supported", () => {
    render(<ApiUsageExample model="azure/gpt-5.4" supportsResponses />);
    expect(screen.getByText("Responses (curl)")).toBeInTheDocument();
    expect(screen.getByText("Responses (Py)")).toBeInTheDocument();
    expect(screen.getByText("Codex")).toBeInTheDocument();
  });

  it("Codex tab offers download + per-OS setup steps", async () => {
    const user = userEvent.setup();
    render(<ApiUsageExample model="azure/gpt-5.4" supportsResponses />);
    await user.click(screen.getByRole("tab", { name: "Codex" }));
    expect(screen.getByText("下載 config.toml")).toBeInTheDocument();
    expect(screen.getByText("安裝與使用步驟")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "macOS" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Linux" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Windows" })).toBeInTheDocument();
    // switching to Windows shows the Windows-style path
    await user.click(screen.getByRole("button", { name: "Windows" }));
    expect(screen.getAllByText(/%USERPROFILE%/).length).toBeGreaterThan(0);
  });
});
