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

  it("warns Windows users to use PowerShell, not cmd", async () => {
    const user = userEvent.setup();
    render(<CodexInstallCard baseUrl="https://ai.example.com/" />);

    // No PowerShell/cmd warning while on the unix tab.
    await user.click(screen.getByRole("button", { name: "macOS / Linux" }));
    expect(screen.queryByText(/PowerShell/)).not.toBeInTheDocument();

    // Switching to Windows surfaces the "use PowerShell, not cmd" hint.
    await user.click(screen.getByRole("button", { name: "Windows" }));
    expect(screen.getAllByText(/PowerShell/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/命令提示字元/).length).toBeGreaterThan(0);
  });

  it("explains what happens for members who already have Codex installed", async () => {
    const user = userEvent.setup();
    render(<CodexInstallCard baseUrl="https://ai.example.com/" />);
    // The note is collapsed behind a summary; expand it.
    await user.click(screen.getByText(/已經裝過 Codex/));
    expect(screen.getByText(/不會重裝/)).toBeInTheDocument();
    // Phase 27: desktop App is now ✓ via shared config (免再設定), not "不建議".
    expect(screen.getByText(/Codex 桌面 App/)).toBeInTheDocument();
    expect(screen.getAllByText(/免再設定/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/不建議/)).not.toBeInTheDocument();
  });

  it("links to the official Codex docs", () => {
    render(<CodexInstallCard baseUrl="https://ai.example.com/" />);
    const link = screen.getByRole("link", { name: /Codex 官方說明/ });
    expect(link).toHaveAttribute("href", "https://developers.openai.com/codex");
    expect(link).toHaveAttribute("target", "_blank");
  });
});
