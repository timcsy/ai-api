# Implementation Plan: 多端點全開（圖片 / rerank / TTS / STT）+ 目錄誠實

**Branch**: `041-multi-endpoint-complete` | **Date**: 2026-06-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/041-multi-endpoint-complete/spec.md`

## Summary

把「多端點開放」主題完整收尾：對成員開放 `/v1/images/generations`（token）、`/v1/rerank`（per-query）、`/v1/audio/speech`（TTS，per-character，**binary 音檔輸出**）、`/v1/audio/transcriptions`（STT，**multipart 音檔上傳**，token 計費），全部走同一條 `run_preflight` + 既有計費一般化（增量②的「數量 + 單位」維度）；並還掉誠實債——`litellm_registry._capabilities` 不再對非 chat mode 兜底 chat、admin 詳情頁顯「類型（kind）」。**零 migration**（`unit`/`price_unit` 字串維度已於 0019 就緒，新單位 query/character 只是字串值）、**零新套件**（litellm `aimage_generation`/`aspeech`/`atranscription` 既有，僅補 `arerank` wrapper）。

binary 兩端的真實形狀已 inspect 驗證：TTS 回 `HttpxBinaryResponseContent.content`（bytes，非串流回傳 → 同請求記帳、無 finally 坑）；STT 收 `UploadFile` → 傳 `file=(filename, bytes)`，回 `TranscriptionResponse(text, usage)`——**無 duration 欄**故 per-second 不可得，STT 改走 token 計費（有 `usage` 就計、whisper 類純 per-second 記 cost 0）。

## Technical Context

**Language/Version**: Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端）
**Primary Dependencies**: FastAPI（含 `UploadFile` multipart）、SQLAlchemy 2.x async、Pydantic v2、`litellm`（`aimage_generation`/`arerank`/`aspeech`/`atranscription` library form）；TanStack Query、shadcn/ui（前端）——**皆既有，不新增套件**
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration**——沿用增量②（0019）的 `call_records.quantity/unit` 與 `price_list.price_unit/price_per_unit_usd`，新單位（query / character）為字串值
**Testing**: pytest（contract + integration）；前端 vitest + Testing Library
**Target Platform**: Linux server（k8s）+ 瀏覽器 SPA
**Performance Goals**: 各端點為一般 proxy 呼叫；TTS 音檔非串流（一次讀 `.content` 回傳，音訊體積小）
**Constraints**: token 計費零回歸；binary I/O 限 TTS（輸出）/STT（輸入）；STT per-second 需音訊長度（無套件不可得）→ 走 token 計費、per-second 延後；非 token 呼叫此階段不被 token 配額擋下；單一 migration head（0019 不變）
**Scale/Scope**: 後端 4 端點（`images`/`rerank`/`audio[speech+transcription]`）+ `upstream.arerank` + `model_kind` 加 `rerank` + `_capabilities` un-fake + admin 詳情 kind；前端 admin 詳情顯類型 + `api-usage-example` 四種範例

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First（NON-NEGOTIABLE）**：✅ 各端點先寫失敗 contract（計量歸戶/拒絕/上游錯誤）；TTS binary 回應、STT multipart 上傳、誠實債（capabilities 不假裝 chat）、token 零回歸皆 test-first。
- **II. 契約優先**：✅ Phase 1 先定四端點契約（含 binary 回應內容類型、multipart 上傳）+ 錯誤格式。
- **III. 整合測試覆蓋外部依賴**：✅ binary 往返（TTS bytes 回傳、STT 上傳→文字）以 contract + mock upstream 驗；計費一般化（query/character 單位）以真實數學驗。
- **IV. 可觀測性**：✅ 四端點成功/失敗皆記 `CallRecord`（含 quantity/unit/cost）；上游錯誤記 `upstream_error` + 去敏 log；**TTS 在 bytes 產出當下記帳**（非 finally，呼應階段 11 串流教訓）。
- **V. YAGNI**：✅ 不新增套件/表/migration；不引入音訊解析（per-second 延後）；不做每單位上限/圖表改版。各端點沿用 `embeddings.py`/`ocr.py` 樣板。

**結論**：無違反，無需 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/041-multi-endpoint-complete/
├── plan.md              # 本檔
├── research.md          # Phase 0：binary 形狀（TTS bytes/STT multipart）、STT 計費單位抉擇、rerank/image 計費、誠實債修法
├── data-model.md        # Phase 1：四單位計量流（無 schema 變更）+ 誠實債的 capabilities/kind
├── quickstart.md        # Phase 1：US1–US5 + token 零回歸
├── contracts/
│   └── endpoints.md     # Phase 1：四端點契約（含 binary/multipart）+ admin 詳情 kind
└── tasks.md             # Phase 2（/speckit.tasks）
```

### Source Code (repository root)

```text
src/ai_api/
├── proxy/
│   ├── images.py         # 新：POST /images/generations（token，沿用 embeddings 樣板）
│   ├── rerank.py         # 新：POST /rerank（per-query，unit="query"）
│   ├── audio.py          # 新：POST /audio/speech（TTS，binary 回應）+ /audio/transcriptions（STT，multipart）
│   └── upstream.py        # 加 arerank + atranscription wrapper（aimage_generation/aspeech 已有，Phase 26）
├── services/
│   ├── model_kind.py      # Kind 加 "rerank"；mode=="rerank" → rerank
│   └── litellm_registry.py # _capabilities 移除 `or ["chat"]`（chat-able 仍 append chat）
├── api/
│   └── catalog.py / admin_catalog.py # admin 詳情序列化加 "kind"（成員面 kind 已存在）
└── main.py                # mount images/rerank/audio routers 於 /v1

tests/
├── contract/
│   ├── test_images.py / test_rerank.py / test_audio.py   # 各端點計量歸戶/拒絕/上游錯誤
│   ├── test_capabilities_honesty.py                       # _capabilities 不假裝 chat + chat 零回歸
│   └── test_catalog_kind.py（擴充）                        # rerank kind + admin 詳情含 kind
└── integration/
    └── test_audio_roundtrip.py                            # TTS bytes 回應 / STT 上傳（mock upstream）

frontend/src/
├── components/api-usage-example.tsx   # 加 image/rerank/tts/stt 範例（依 kind）
├── routes/catalog-detail.tsx          # 依 kind 傳對應範例
├── routes/admin/catalog-*.tsx         # admin 詳情顯「類型（kind）」
└── __tests__/...                       # 範例 + admin 類型顯示測試
```

**Structure Decision**: web application。四端點各一個 proxy 檔（沿用 `ocr.py`/`embeddings.py` 樣板，原則 7「加端點 ≈ 同一條 preflight + litellm 函式 + 記帳」）；audio 的 TTS+STT 同檔（同一資源族）。計費全用增量②的單位維度。誠實債橫切 `litellm_registry` + 目錄序列化 + 前端詳情。

## Complexity Tracking

> 無 Constitution 違反，無需填寫。
