import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ApplicationsPage } from "@/routes/apps";

describe("<ApplicationsPage /> storefront (Phase 28)", () => {
  it("renders an app tile grid with a Codex tile linking to its detail page", () => {
    const qc = new QueryClient();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/apps"]}>
          <Routes>
            <Route path="/apps" element={<ApplicationsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByText("應用")).toBeInTheDocument();
    const tile = screen.getByRole("link", { name: "Codex" });
    expect(tile).toHaveAttribute("href", "/apps/codex");
  });
});
