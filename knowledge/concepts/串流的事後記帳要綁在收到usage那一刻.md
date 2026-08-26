# 串流的事後記帳要綁在「收到 usage 那一刻」，不是 generator 生命週期結尾

**可判斷主張**：拿一段串流端點的計費/稽核問「它是在解析到 usage/`response.completed` 的當下、用 fresh
session 立即記帳，還是拖到 `finally`？」——前者屬這個概念；放在 `finally`、或用 `except Exception` 想涵蓋
取消，就是反例（用量會默默消失）。

## 一句話

串流端點的副作用要綁在「資料已到且連線仍在」的那個事件點；結尾很可能在 client 斷線的 cancellation 下執行，
DB await 會被打斷。

## 為什麼是它（剪枝力）

- Codex/SDK 收到最後一個 event 後**立刻斷線** → Starlette 取消串流任務 → `finally` 在 `CancelledError` 情境執行。
  `CancelledError` 在 Python 3.11 繼承 **`BaseException`**（不是 `Exception`）→ `except Exception` 接不到 →
  `await session.commit()` 被中斷 → 那筆用量默默消失、連 error log 都沒有。
- curl 會讀到串流尾才關、generator 正常 exhaust，所以「測得到、Codex 卻記不到」極難察覺。
- 請求 session 在 StreamingResponse body 執行時已關 → 記帳一律**開新 fresh session**。
- `finally` 只留 best-effort 後援且 `except BaseException` 並 log，不靜默吞掉。
- **usage chunk 形狀別假設**：OpenAI 標準「沒要就不送、要的話最後一個 chunk `choices:[]`+usage」，但 Azure/litellm
  把 usage 掛在 `choices` 非空的 chunk 上——改成「任何帶 usage 的 chunk 就把 `usage` 設 null 再轉發」，gateway
  才能自己 include_usage 計費、又幫沒要的 client 過濾。

## 兩弧同款坑

responses（Arc 4，階段 11 Codex 真機暴露）與 chat/completions（Arc 8，補串流時）踩同一坑——後者的 `stream:true`
原本被靜默吞、回整包 JSON（註解寫「各有 handler」只是意圖、沒真做）。

## 投影到三觀點

- **principles**：原則 2（可追蹤性——用量不能默默消失）。
- **vision**：〈架構〉對外 API 的 SSE streaming。
- **history / experience**：experience「串流端點的副作用要綁在資料已到且連線仍在的事件點」。

## 指回

- `proxy/responses.py`、`proxy/chat.py` `_record_fresh`；`concepts/加一個同形態端點應該等於加一筆資料.md`
  （串流端點刻意不納入 registry 的原因）。
