import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiUsageExample } from "@/components/api-usage-example";

describe("<ApiUsageExample />", () => {
  it("shows only chat tabs when responses unsupported", () => {
    render(<ApiUsageExample model="azure/gpt-4o" />);
    expect(screen.getByText("curl")).toBeInTheDocument();
    expect(screen.queryByText(/Responses \(curl\)/)).not.toBeInTheDocument();
  });

  it("adds Responses tabs when supported (Codex setup moved to the install card)", () => {
    render(<ApiUsageExample model="azure/gpt-5.4" supportsResponses />);
    expect(screen.getByText("Responses (curl)")).toBeInTheDocument();
    expect(screen.getByText("Responses (Py)")).toBeInTheDocument();
    // Phase 20: the per-model Codex config tab was removed; no Codex tab remains.
    expect(screen.queryByRole("tab", { name: "Codex" })).not.toBeInTheDocument();
  });

  // Phase 29
  it("shows /embeddings example for embedding models", () => {
    render(<ApiUsageExample model="azure/text-embedding-3" isEmbedding />);
    expect(screen.getByText(/向量（embedding）模型/)).toBeInTheDocument();
    expect(screen.getAllByText(/\/embeddings/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/messages/)).not.toBeInTheDocument();
  });

  it("shows chat example (not embeddings) for non-embedding models", () => {
    render(<ApiUsageExample model="azure/gpt-x" />);
    expect(screen.getByText(/messages/)).toBeInTheDocument();
    expect(screen.queryByText(/向量（embedding）模型/)).not.toBeInTheDocument();
  });

  // Phase 29 ②
  it("shows /ocr example for OCR models", () => {
    render(<ApiUsageExample model="azure/mistral-document-ai" isOcr />);
    expect(screen.getByText(/文件辨識（OCR）模型/)).toBeInTheDocument();
    expect(screen.getAllByText(/\/ocr/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/document/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/messages/)).not.toBeInTheDocument();
  });

  // Phase 29 ③
  it.each([
    ["image", /images\/generations/, /prompt/],
    ["rerank", /\/rerank/, /documents/],
    ["tts", /audio\/speech/, /voice/],
    ["stt", /audio\/transcriptions/, /file=@/],
    ["moderation", /\/moderations/, /input/],
    ["search", /\/search/, /query/],
    ["image_edit", /images\/edits/, /image=@/],
  ])("shows the right example for kind=%s", (kind, pathRe, bodyRe) => {
    render(<ApiUsageExample model="azure/m" kind={kind as string} />);
    expect(screen.getAllByText(pathRe as RegExp).length).toBeGreaterThan(0);
    expect(screen.getAllByText(bodyRe as RegExp).length).toBeGreaterThan(0);
    expect(screen.queryByText(/messages/)).not.toBeInTheDocument();
  });
});
