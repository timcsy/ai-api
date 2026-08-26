# 2026-05-26 · auto-tag 的一條錯誤路徑揭露全站潛伏 bug

## 為何（why）
階段 5.2（spec 014）在規則頁送惡意 regex，後端**正確**回 422 + 具體訊息（`nested quantifier (ReDoS risk)`），
但 UI 只跳無資訊的「建立失敗」。

## 怎麼（how）
追查發現兩種錯誤封包並存：proxy 回 `{error:{...}}`，FastAPI `HTTPException(detail=...)` 包成
`{detail:{error:{...}}}`；api-client 只認前者 → **所有走 HTTPException 的 admin 錯誤訊息**都被降級成空的
`statusText`——潛伏已久（成功路徑不受影響），一條為 auto-tag 而測的錯誤路徑把它揪出來。

## 用了哪些概念
「錯誤封包 shape 是跨層契約，兩種 envelope 都要解析」「新端點上線順手驗一次錯誤路徑訊息真的有顯示」。

## 結果
修 `api-client.ts`（`body.error ?? body.detail?.error`）。收於 [`history/lessons-archive.md`](../history/lessons-archive.md)；
呼應 experience「後端有 API ≠ 使用者用得到」的孿生——「後端訊息對了 ≠ 使用者看得到」。
