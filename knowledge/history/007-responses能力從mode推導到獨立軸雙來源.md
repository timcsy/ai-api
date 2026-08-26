# 007：responses 能力從「mode 推導」到「獨立軸 + 實測/手動雙來源」
> 日期：2026-06-08

## 轉移
- 舊（superseded）：階段 24 一度把 `responses`（能不能走 `/v1/responses`）從 LiteLLM `mode` 推導、塞進
  「模型能力（capabilities）」清單，並以靜態能力旗標**事前硬擋**。
- 新（spec 035 / 階段 25）：三軸解耦——responses 是**我們 gateway 的端點可用性**（軸③），由**實測 + 手動**
  雙來源判定；LiteLLM 完全不碰 responses、採納改 merge-preserve；runtime **軟化事前閘門**（不再因缺靜態旗標
  事前擋，唯一事前擋＝admin 手動標 blocked）。

## 為什麼變
把軸③（我們的、可實測可覆寫）塞進軸②（外部同步管轄）＝把易變核心綁到快變邊緣：LiteLLM 同步一動 capabilities
就把 admin 設的 responses 洗掉 → Codex 突然不能用（作者明列為 latent bug）。靜態能力旗標會過時、會被洗、會誤擋
實際打得通的模型。「能力不確定 → 打一次就知道」。此轉移後被蒸餾成**原則 7 演進性**（守住軸的正交、實測勝於臆測）。

## 狀態
✅ 已採用。`mode → responses` 衍生 ⚰️ 移除（見 `tombstones.md`）。同形狀在階段 32 realtime 重現（能力軸非 mode）。
