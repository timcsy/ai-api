# Quickstart 驗收：多端點全開 + 目錄誠實

> 前置：admin 已登入；目錄各有一個對應 mode 的模型（image_generation / rerank / audio_speech / audio_transcription）+ provider credential。

## US1 圖片（P1）
1. 成員領圖片模型分配+金鑰 → `POST /v1/images/generations {model, prompt}`。
2. 回圖片資料（b64/url）；用量記一筆 token 計費歸戶。

## US2 rerank（P2）
1. 領 rerank 模型金鑰 → `POST /v1/rerank {model, query, documents}`。
2. 回排序結果；用量記 `unit="query"` quantity=1、按每查詢價計費。(admin 可在價格頁設每查詢價，同 OCR 每頁價)

## US3 TTS（P3）
1. 領 TTS 模型金鑰 → `POST /v1/audio/speech {model, input, voice}`。
2. **回音檔 bytes**、`Content-Type: audio/mpeg`（存成 .mp3 可播）；用量記 `unit="character"` quantity=輸入字數。

## US4 STT（P4）
1. 領 STT 模型金鑰 → `POST /v1/audio/transcriptions`（multipart：`model` + `file`=音檔）。
2. 回辨識文字（JSON）；用量記 token 計費（token-計價模型完整、whisper 類 cost 0）。

## US5 目錄誠實（P3）
1. admin 看 OCR/embedding/rerank 等模型詳情 → 「能力」欄**不再顯 chat**（無旗標時空）、有「**類型**」欄（OCR/rerank/…）。
2. chat 模型 → 能力仍含 chat（零回歸）。
3. 既有被誤標 chat 的模型 → 「檢查 LiteLLM 更新」重新採納 → 能力更新。

## 零回歸（SC-005 / SC-006）
- 既有 chat/responses/embedding/OCR 呼叫、token 計費、用量、配額、**能力 facet 篩選** 不變。
- `python -m pytest tests/ -q` 全綠；`ruff check .`（含 tests）+ `mypy` 乾淨；`alembic heads`=`0019`（無新 migration）；無新套件。
- 前端 `npx tsc --noEmit && npm run build && npm test -- --run` 全綠。
- 真機煙霧：四端點壞 token → 401（皆走 `location /v1`）。
