import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { LiteLLMRawPanel } from "@/components/litellm-raw-panel";

describe("<LiteLLMRawPanel />", () => {
  it("shows the full raw entry on expand", async () => {
    render(<LiteLLMRawPanel raw={{ mode: "chat", max_output_tokens: 16384, supports_vision: true }} />);
    await userEvent.click(screen.getByText(/LiteLLM 原始資訊/));
    expect(screen.getByText("mode")).toBeInTheDocument();
    expect(screen.getByText("16384")).toBeInTheDocument();
    expect(screen.getByText("max_output_tokens")).toBeInTheDocument();
  });

  it("renders nothing when raw is empty or missing", () => {
    const { container, rerender } = render(<LiteLLMRawPanel raw={null} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<LiteLLMRawPanel raw={{}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
