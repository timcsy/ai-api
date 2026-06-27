import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { UsageExplorer } from "@/components/usage-explorer";

describe("<UsageExplorer />", () => {
  it("shows a model selector and a usage example for the selected model", () => {
    render(
      <UsageExplorer
        models={[{ slug: "azure/gpt-5.4-mini", label: "GPT 5.4 mini", kind: "chat", supportsResponses: true }]}
        emptyHint="無"
      />,
    );
    expect(screen.getByLabelText("選擇模型")).toBeInTheDocument();
    // the example (single shared ApiUsageExample) renders the selected model slug
    expect(document.body.textContent).toContain("azure/gpt-5.4-mini");
  });

  it("renders the empty hint when the key/member has no usable model", () => {
    render(<UsageExplorer models={[]} emptyHint="這把金鑰目前沒有可用的模型" />);
    expect(screen.getByText("這把金鑰目前沒有可用的模型")).toBeInTheDocument();
    expect(screen.queryByLabelText("選擇模型")).not.toBeInTheDocument();
  });
});
