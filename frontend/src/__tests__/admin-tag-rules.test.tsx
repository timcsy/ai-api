import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "@/components/ui/toaster";
import { AdminTagRulesPage } from "@/routes/admin/tag-rules";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AdminTagRulesPage />
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("<AdminTagRulesPage />", () => {
  it("shows empty state when no rules exist", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(200, []));
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/還沒有規則/)).toBeInTheDocument(),
    );
  });

  it("renders rules in order with tag and pattern", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(200, [
        {
          id: "r1", order_index: 0, matcher_type: "email_localpart_regex",
          pattern: "^(?:[a-z]{0,2}\\d{6,})$", tag: "student", enabled: true,
          created_at: "2026-05-26T00:00:00Z", created_by: "admin",
        },
        {
          id: "r2", order_index: 1, matcher_type: "always",
          pattern: "", tag: "teacher", enabled: true,
          created_at: "2026-05-26T00:00:00Z", created_by: "admin",
        },
      ]),
    );
    renderPage();
    expect(await screen.findByText("student")).toBeInTheDocument();
    expect(screen.getByText("teacher")).toBeInTheDocument();
    expect(screen.getByText(/Fallback/)).toBeInTheDocument();
  });

  it("surfaces unsafe_regex error from create", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    // initial list (empty), then create returns 422 unsafe_regex
    fetchMock.mockResolvedValueOnce(jsonResponse(200, []));
    fetchMock.mockResolvedValueOnce(
      jsonResponse(422, { detail: { error: { code: "unsafe_regex", message: "nested quantifier (ReDoS risk)" } } }),
    );
    renderPage();

    await screen.findByText(/還沒有規則/);
    fireEvent.click(screen.getByText("新增規則"));
    fireEvent.change(screen.getByPlaceholderText(/\[a-z\]/), { target: { value: "(a+)+" } });
    fireEvent.change(screen.getByPlaceholderText(/student \/ teacher/), { target: { value: "bad" } });
    fireEvent.click(screen.getByText("建立"));

    await waitFor(() =>
      expect(screen.getByText(/nested quantifier/)).toBeInTheDocument(),
    );
  });

  it("shows the test-email match result", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    fetchMock.mockResolvedValueOnce(jsonResponse(200, []));  // rules list
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, { matched: true, rule_id: "r1", tag: "student", matcher_type: "email_localpart_regex" }),
    );
    renderPage();

    await screen.findByText(/還沒有規則/);
    fireEvent.change(screen.getByPlaceholderText("b10901234@school.edu"), {
      target: { value: "b10901234@school.edu" },
    });
    fireEvent.click(screen.getByText("測試"));

    await waitFor(() => expect(screen.getByText("student")).toBeInTheDocument());
  });
});
