import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FieldSourceBadge } from "@/components/field-source-badge";

describe("<FieldSourceBadge />", () => {
  it("labels each source", () => {
    const { rerender } = render(<FieldSourceBadge source="litellm" />);
    expect(screen.getByText("LiteLLM")).toBeInTheDocument();
    rerender(<FieldSourceBadge source="borrowed" />);
    expect(screen.getByText("借用")).toBeInTheDocument();
    rerender(<FieldSourceBadge source="manual" />);
    expect(screen.getByText("手動")).toBeInTheDocument();
  });

  it("renders nothing when source is undefined (no LiteLLM provenance)", () => {
    const { container } = render(<FieldSourceBadge source={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});
