# 009：端點從「一個個手寫 handler」到「資料驅動 registry」
> 日期：2026-06-11

## 轉移
- 舊（superseded）：階段 29 一個個手寫了 7 個 proxy 端點（chat/responses/embedding/ocr/image/rerank/audio），
  結構幾乎複製貼上（~741 行）。
- 新（spec 042 / 階段 31）：收斂成 `proxy/engine.py`（唯一執行流程）+ `endpoint_spec.py`（三軸 IOShape × Meter
  × 上游 call）+ `registry.py`（`EndpointSpec` 註冊表）。「加同形態端點＝加一筆資料」。

## 為什麼變
複製貼上的結構是「同一概念該抽共用」的訊號（原則 5 + 原則 7）。判準：加端點應該是加一筆資料、不是複製一個檔。
驗證：moderation（純 JSON/token）＝最小案例；search（上游用 `search_provider` 非 model）＝各異的請求→上游對映；
image_edit（multipart+每張圖）＝形態軸可擴。**零回歸鐵證**：遷移 5 端點時 contract/integration 測試一行斷言
都不改、git diff 為空。

## 為什麼串流端點刻意排除
chat/responses **不納入 registry**（spec 042 R1）——串流中記帳、執行形態不同，handler 零觸碰＝零回歸。

## 狀態
✅ 已採用。原則 7 四手法齊發（資料勝於程式 + 註冊表 + 軸正交 + 適配層）。
