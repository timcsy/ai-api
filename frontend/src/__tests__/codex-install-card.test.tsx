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
});
