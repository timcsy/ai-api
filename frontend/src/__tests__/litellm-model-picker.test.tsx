import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LiteLLMModelPicker, type LitellmDraft } from "@/components/litellm-model-picker";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("<LiteLLMModelPicker />", () => {
  it("searches the registry and brings a model's draft back via onPick", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.includes("/admin/catalog/litellm/search")) {
        return jsonResponse(200, {
          results: [
            { key: "azure/gpt-4o", provider: "azure", mode: "chat", context_window: 128000,
              supports_vision: true, suggested_price: { input_per_1k: "0.0025", output_per_1k: "0.01", cached_input_per_1k: "0.00125" } },
          ],
        });
      }
      if (url.includes("/admin/catalog/litellm/suggest/")) {
        return jsonResponse(200, {
          key: "azure/gpt-4o", slug_default: "azure/gpt-4o",
          metadata: { context_window: 128000, modality_input: ["text", "image"], modality_output: ["text"], capabilities: ["chat", "vision"] },
          suggested_price: { input_per_1k: "0.0025", output_per_1k: "0.01", cached_input_per_1k: "0.00125" },
          imported_version: "1.85.1",
        });
      }
      return jsonResponse(404, { error: {} });
    });

    const picked: LitellmDraft[] = [];
    const user = userEvent.setup();
    render(<LiteLLMModelPicker onPick={(d) => picked.push(d)} />);

    await user.type(screen.getByPlaceholderText(/搜尋模型/), "gpt-4o");
    await user.click(screen.getByRole("button", { name: "搜尋" }));
    await waitFor(() => expect(screen.getByText("azure/gpt-4o")).toBeInTheDocument());

    await user.click(screen.getByText("azure/gpt-4o"));
    await waitFor(() => expect(picked.length).toBe(1));
    expect(picked[0]!.key).toBe("azure/gpt-4o");
    expect(picked[0]!.metadata.context_window).toBe(128000);
    expect(picked[0]!.suggested_price?.input_per_1k).toBe("0.0025");
  });
});
