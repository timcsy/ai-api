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

// Plain-language 一句話說明：給不熟 AI 術語的人 hover 時看得懂「這個能力能做什麼」。
// 用於 facet 標籤與能力徽章的 title（原生 hover 提示，無額外套件）。未列出者回空字串。
export const FACET_HINTS: Record<string, string> = {
  // modality
  text: "可以輸入文字（一般的文字提問／指令）。",
  image: "可以輸入圖片，讓模型「看圖」回答（看照片、截圖、圖表）。",
  audio: "可以輸入語音／音訊（例如把錄音轉成文字）。",
  embedding: "把文字轉成向量，用於搜尋、相似度比對、分類（不是聊天）。",
  // capabilities
  chat: "一般對話問答，最常用的模式。",
  responses: "可用於 Codex／Agent 工具（走 /v1/responses 端點）。要讓 Codex 接得上就選這個。",
  vision: "看得懂圖片內容，能描述、辨識、讀圖中文字。",
  "function-calling": "能依你定義的工具自動產生呼叫參數，串接你的程式或外部服務。",
  "tool-use": "能使用外部工具／函式來完成任務。",
  "json-mode": "保證輸出合法 JSON，方便程式直接解析。",
  streaming: "逐字即時輸出，不必等整段生成完才看到結果。",
  reasoning: "會做多步推理，適合數學、邏輯、較難的問題。",
  pdf: "能直接讀 PDF 檔內容來回答。",
  "prompt-caching": "重複的長提示可快取，後續呼叫更快、更省成本。",
  "web-search": "能上網查最新資料再回答。",
  video: "可以輸入影片內容。",
  "structured-output": "能依指定結構（schema）輸出，欄位穩定可預期。",
  "computer-use": "能操作電腦介面（點擊、輸入）來代你完成操作。",
  "code-execution": "能實際執行程式碼並回傳結果。",
  // cost_tier
  low: "相對便宜，適合大量、簡單的任務。",
  medium: "成本與能力折衷。",
  high: "最強但較貴，留給困難或重要的任務。",
};

export function facetHint(value: string): string {
  return FACET_HINTS[value] ?? FACET_HINTS[value.replace(/_/g, "-")] ?? "";
}

export function facetLabel(value: string): string {
  // Catalog data may carry either hyphenated (function-calling, prompt-caching)
  // or underscored (function_calling, prompt_caching) capability vocab depending
  // on how the row was created. Labels are keyed by the hyphenated form, so
  // normalize underscores → hyphens before lookup. Display-only; data untouched.
  return FACET_LABELS[value] ?? FACET_LABELS[value.replace(/_/g, "-")] ?? value;
}
