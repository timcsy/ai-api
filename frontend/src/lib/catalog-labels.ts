// Display-only 中文對照：catalog 的 facet 值（modality / capability / cost_tier /
// recommended_for）在 API 與 query 參數中仍是英文識別字（如 ?capability=vision），
// 只有畫面上的標籤翻成中文，讓不熟術語的初學者也看得懂。未列出的值原樣顯示。
export const FACET_LABELS: Record<string, string> = {
  // modality
  text: "文字",
  image: "圖片",
  audio: "語音",
  embedding: "向量嵌入",
  // capabilities
  chat: "對話",
  responses: "Agent 相容（Responses）",
  vision: "影像辨識",
  "function-calling": "函式呼叫",
  "tool-use": "工具使用",
  "json-mode": "JSON 模式",
  streaming: "串流輸出",
  reasoning: "推理",
  pdf: "PDF 解析",
  "prompt-caching": "提示快取",
  "web-search": "網路搜尋",
  video: "影片",
  "structured-output": "結構化輸出",
  "computer-use": "電腦操作",
  "code-execution": "程式執行",
  // cost_tier
  low: "低",
  medium: "中",
  high: "高",
  // recommended_for
  agent: "Agent 代理",
  classification: "文本分類",
  code: "程式撰寫",
  "cost-effective": "高性價比",
  flagship: "旗艦首選",
  "image-gen": "圖片生成",
  "image-generation": "圖片生成",
  "long-context": "長文本",
  multimodal: "多模態",
  speech: "語音",
  stt: "語音轉文字",
  summarization: "文件摘要",
  translation: "翻譯",
  tts: "文字轉語音",
};

export function facetLabel(value: string): string {
  return FACET_LABELS[value] ?? value;
}
