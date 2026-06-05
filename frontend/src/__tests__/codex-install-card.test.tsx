import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CodexInstallCard } from "@/components/codex-install-card";

vi.mock("@/lib/clipboard", () => ({ copyToClipboard: vi.fn().mockResolvedValue(undefined) }));
import { copyToClipboard } from "@/lib/clipboard";

describe("<CodexInstallCard />", () => {
  it("shows the per-OS one-line command and copies it", async () => {
    const user = userEvent.setup();
    render(<CodexInstallCard baseUrl="https://ai.example.com/" />);

    // macOS/Linux → curl one-liner.
    await user.click(screen.getByRole("button", { name: "macOS / Linux" }));
    expect(
      screen.getByText("curl -fsSL https://ai.example.com/install/codex.sh | sh"),
    ).toBeInTheDocument();

    // Switch to Windows → PowerShell one-liner.
    await user.click(screen.getByRole("button", { name: "Windows" }));
    expect(
      screen.getByText("irm https://ai.example.com/install/codex.ps1 | iex"),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "複製" }));
    expect(copyToClipboard).toHaveBeenCalledWith(
      "irm https://ai.example.com/install/codex.ps1 | iex",
    );
  });

  it("explains what happens for members who already have Codex installed", async () => {
    const user = userEvent.setup();
    render(<CodexInstallCard baseUrl="https://ai.example.com/" />);
    // The note is collapsed behind a summary; expand it.
    await user.click(screen.getByText(/已經裝過 Codex/));
    expect(screen.getByText(/不會重裝/)).toBeInTheDocument();
    // Desktop app is explicitly called out as NOT supported (account-bound).
    expect(screen.getByText(/Codex 桌面 App/)).toBeInTheDocument();
  });
});
