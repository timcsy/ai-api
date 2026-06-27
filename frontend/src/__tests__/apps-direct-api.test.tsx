import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { APPLICATIONS } from "@/lib/applications";
import { ApplicationsPage } from "@/routes/apps";

describe("應用商店 — 直接用 API / SDK (Phase 34)", () => {
  it("registry includes both a tool (Codex) and the Direct API/SDK app", () => {
    const ids = APPLICATIONS.map((a) => a.id);
    expect(ids).toContain("codex");
    expect(ids).toContain("api");
  });

  it("apps page shows the tool card and the Direct API / SDK card side by side", () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/apps"]}>
          <ApplicationsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByText("Codex")).toBeInTheDocument();
    expect(screen.getByText("直接用 API / SDK")).toBeInTheDocument();
  });
});
