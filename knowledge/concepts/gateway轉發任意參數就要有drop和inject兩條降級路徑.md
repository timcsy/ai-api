# gateway 轉發任意參數給任意模型，就要有 drop 和 inject 兩條降級路徑

**可判斷主張**：拿一段「gateway 把 client 參數交給上游」的處理問「它同時處理了『多餘的參數被上游拒』與
『缺必填參數』兩面，且靠上游錯誤訊息反應式重試、而非維護每模型參數表嗎？」——是，屬這個概念；只做單面、
或靠靜態模型表，就是反例。

## 一句話

轉發任意參數給任意模型 = 一定會撞到「某模型不吃/缺某參數」；**多餘的要 drop、缺的要 inject**，是同一枚硬幣兩面。

## 為什麼是它（剪枝力）

- 補 chat 參數 passthrough 後：① 推理模型只吃 `temperature=1`，client 送 `0.4` → Azure 400 → 我方 502（自己引入
  的回歸，多餘要 drop）；② diarization 缺必填 `chunking_strategy` → 同樣 502（缺的要 inject）。
- **關鍵**：litellm 的 `drop_params` **依賴它的內建模型表**，對「使用者自訂的 Azure deployment 名」（任意別名、
  無法反推底層模型）**無效**。真正 provider-agnostic 的作法是**反應式重試**——catch 上游 400 → 從錯誤訊息 regex
  出 param 名 → drop/inject 該參數 → 重試（每次一個、有界終止）。
- **不重複計費**：只在成功後記帳；失敗路徑（pre-inference、無 token）不寫 record。
- **未來優化**：目錄已有 `reasoning` 標記，可據此**預先**不送 temperature 省一次往返——但反應式重試是必留的保險網。
- **選填 pass-through 的孿生坑**：資料驅動端點的 `call` lambda 很容易只 forward 必填、靜默吞掉選填
  （`/v1/ocr` 丟掉 `include_image_base64`/`pages`）；用白名單 pass-through、審端點時逐一對上游 API。

## 投影到三觀點

- **principles**：原則 7（provider-agnostic、資料驅動、實測勝於臆測）。
- **vision**：〈架構〉「反應式參數協商」段。
- **history**：`016-Dockerfile...`? 否——屬 Arc 8 維護；見 `history/completed-phases-detail.md` 階段 44 後維護段。

## 指回

- `concepts/加一個同形態端點應該等於加一筆資料.md`（`call` 可是有狀態 async 函式）
- experience「gateway 轉發任意參數 → 反應式重試」；debug「參數在哪層不見」用分段各自證。
