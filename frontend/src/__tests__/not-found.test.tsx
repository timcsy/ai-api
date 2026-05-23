import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { NotFoundPage } from "@/routes/not-found";

describe("<NotFoundPage />", () => {
  it("renders 404 + link back to home", () => {
    render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("404")).toBeInTheDocument();
    expect(screen.getByText("找不到頁面")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "回首頁" })).toHaveAttribute("href", "/");
  });
});
