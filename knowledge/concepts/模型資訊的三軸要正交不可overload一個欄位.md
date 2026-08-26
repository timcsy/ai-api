# 模型資訊的三軸要正交，不可把一軸 overload 進另一軸的欄位

**可判斷主張**：拿一個模型狀態欄位問「它描述的是①模型原生 API 型態、②模型能力、③我們 gateway 的端點
可用性、還是④客戶端工具？」——若答案唯一且該欄位只承載那一軸，屬這個概念；若一個欄位同時被兩軸寫、或
某軸從另一軸「推導」出來，就是反例（latent bug）。

## 一句話

模型資訊有正交的多軸；把「我們的、可實測可覆寫」的軸塞進「外部同步管轄」的軸，同步一動就會互洗。

## 三軸（本專案的正交分解）

1. **模型原生 API 型態**：LiteLLM `mode`（唯讀快照）。
2. **模型能力**：LiteLLM 旗標（vision/reasoning/pdf…）。
3. **我們 gateway 的端點可用性**：responses、realtime 等，由**實測 + 手動**雙來源判定（我們自己的軸）。
4. （+客戶端工具軸：Codex/Copilot 等如何接。）

## 為什麼是它（剪枝力）

- **latent bug 的根**：階段 24 一度把 `responses` 從 `mode` 推導、塞進「能力」清單 → LiteLLM 同步一動就把 admin
  設的 responses 洗掉 → Codex 突然不能用。realtime 同理是能力軸（讀 `supported_endpoints`）非 `mode`
  （whisper-1 與 gpt-realtime-whisper 同 mode、能力不同）。
- **對策**：三軸解耦；軸③由 runtime 實測（打通就用、打不通回真實 `upstream_error`）+ admin 手動覆寫，
  LiteLLM 完全不碰軸③，採納改 merge-preserve（不動 manual 欄）。「能力不確定 → 打一次就知道」。

## 投影到三觀點

- **principles**：原則 7（守住軸的正交、實測勝於臆測、資料勝於程式）。
- **vision**：〈架構〉的 responses/realtime 判定；responses_support 承載於既有 capabilities JSON 的內部標記。
- **history**：`007-responses能力從mode推導到獨立軸雙來源.md`。

## 指回

- `history/007-responses能力從mode推導到獨立軸雙來源.md`、`concepts/加一個同形態端點應該等於加一筆資料.md`
- experience「別 overload 既有欄位——先問這是哪條軸」。
