# Arc 6（多端點/資料驅動 registry/計費一般化/成本制配額）未決項快照

> 怎麼冒出來的：migrate 從 arc-6〈開放〉搬下（截至 `fca0cd0`，2026-06-13）。

- 〔仍開放〕**image_edit / search 真分支未實測**：Azure 不提供，待接非 Azure provider 才能真打（架構就緒、
  recipe 待補真分支）。
- 〔仍開放/descope〕**video_generation**：async job 子系統，明確 descope，未來按需以獨立子專案評估（見 tombstones）。
- 〔仍開放/傾向不做〕**vector_store**：不符 per-call 計量歸戶模型，傾向誠實不做、未定案。
- 〔仍開放/延後〕**STT per-second 計量**：需「音訊長度來源 / 新依賴」決策才能開（見 tombstones）。
- 〔仍開放〕**(推測) 非 token 端點的「每單位濫用上限」（每天 N 張/頁）**：階段 33 以 USD 月度統一解掉主線，
  per-unit 日上限維持 descope；是否未來真需要日粒度，作者留「再另議」。
