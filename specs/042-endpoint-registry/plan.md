# Implementation Plan: 統一端點架構（資料驅動 registry）+ moderation / search / image_edit

**Branch**: `042-endpoint-registry` | **Date**: 2026-06-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/042-endpoint-registry/spec.md`

## Summary

把 5 個**非串流**成員推論端點（embeddings / ocr / images / rerank / audio〔tts+stt〕，~741 行、~80% 複製貼上）收斂成一條**共用執行引擎 + 少數 I/O 形態處理器 + EndpointSpec 註冊表（資料）**，並以此架構新增三個同步推論端點：moderation（token）、search（每查詢、上游參數對映各異）、image_edit（multipart 上傳、每張圖）。**串流端點（chat/responses）刻意不納入**——它們在串流中記帳（階段 11 教訓：在 `response.completed` 當下記、非事後），與「上游回傳→記帳→回應」的引擎形態根本不同，強塞會破壞既有正確性；保持零觸碰＝零回歸。**零 migration、零套件**（multipart 階段 29③ 已備）。

架構＝三軸正交（原則 7）：**① I/O 形態**（輸入 JSON/multipart × 輸出 JSON/binary）**② 計量策略**（TokenMeter 讀 usage／UnitMeter(unit, 數量函式)）**③ 上游呼叫**（每端點一個小 `call` 對映：model+input / search_provider+query / image+prompt）。加同形態端點＝加一筆 `EndpointSpec` 資料。

## Technical Context

**Language/Version**: Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端少量範例）
**Primary Dependencies**: FastAPI（含 `UploadFile` multipart，既有）、SQLAlchemy 2.x async、Pydantic v2、`litellm`（`amoderation`/`asearch`/`aimage_edit` 既有函式）；TanStack Query、shadcn/ui（前端）——**皆既有，不新增套件**
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表/欄/migration**——沿用 0019 的 `call_records.{quantity,unit}` 與 `price_list.{price_unit,price_per_unit_usd}`，新單位 `image`/`query` 為字串值
**Testing**: pytest（contract + integration）；既有端點測試＝重構金鋼罩；前端 vitest
**Target Platform**: Linux server（k8s）+ 瀏覽器 SPA
**Performance Goals**: 引擎為純函式組裝，無額外延遲；非串流端點一次取回再記帳
**Constraints**: **既有 5 端點外部行為零回歸**（測試不改斷言）；chat/responses 零觸碰；binary 限 tts 輸出、multipart 限 stt/image_edit 輸入；單一 migration head（0019）
**Scale/Scope**: 後端新增引擎 + 形態/計量策略 + 8 筆 EndpointSpec（5 既有遷移 + 3 新）；前端 `api-usage-example` 加三種範例

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First（NON-NEGOTIABLE）**：✅ 引擎/形態/計量先寫單元測試；三新端點先寫失敗 contract；重構以**既有測試全綠不改斷言**為驗收（行為不變的證明）。
- **II. 契約優先**：✅ Phase 1 先定 EndpointSpec 結構 + 三新端點外部契約（含 multipart）+ 錯誤格式。
- **III. 整合測試覆蓋外部依賴**：✅ 三新端點 mock upstream 驗計量歸戶；重構後既有 contract/integration 全跑（真實 DB 計費）。
- **IV. 可觀測性**：✅ 引擎統一記 `CallRecord`（quantity/unit/cost）+ 上游錯誤 `upstream_error` + 去敏；行為與既有一致。
- **V. YAGNI**：✅ 只抽「已重複 5 次」的非串流流程（憲章「三段相似可保留、第四個再抽」早已滿足）；不為串流/async/ws 預留抽象（不在範圍）；不過度泛化 EndpointSpec（只含實際需要的欄位）。

**結論**：無違反，無需 Complexity Tracking。串流端點不納入是**範圍決策**（見 research R1），非複雜度規避。

## Project Structure

### Documentation (this feature)

```text
specs/042-endpoint-registry/
├── plan.md              # 本檔
├── research.md          # Phase 0：registry 範圍（排除串流）、三軸抽象、三新端點形狀、零回歸策略
├── data-model.md        # Phase 1：EndpointSpec / Meter / IOShape 結構（無 DB 變更）
├── quickstart.md        # Phase 1：US1（既有零回歸）+ US2–US4 + 加端點=加資料 驗收
├── contracts/
│   └── endpoints.md     # Phase 1：moderation/search/image_edit 契約 + EndpointSpec 內部契約
└── tasks.md             # Phase 2（/speckit.tasks）
```

### Source Code (repository root)

```text
src/ai_api/proxy/
├── engine.py             # 新：共用執行引擎 run_endpoint(spec, request/parts, auth, session)
├── endpoint_spec.py      # 新：EndpointSpec dataclass + IOShape（輸入/輸出）+ Meter（Token/Unit）
├── registry.py           # 新：8 筆 EndpointSpec 註冊 + build_router() 產生 APIRouter
├── embeddings.py ocr.py images.py rerank.py audio.py  # 刪除（遷移成 registry 內的 spec）
├── router.py responses.py  # 不動（串流端點，零觸碰）
└── upstream.py            # 加 amoderation / asearch / aimage_edit wrapper

src/ai_api/main.py         # 改：mount registry.build_router() 取代 5 個 *_router

tests/
├── unit/
│   └── test_endpoint_engine.py   # 引擎/Meter/IOShape 單元（先寫）
├── contract/
│   ├── test_moderation.py test_search.py test_image_edit.py  # 三新端點（先寫）
│   └── test_{embeddings,ocr,images,rerank,audio}.py          # 既有 → 重構金鋼罩（不改斷言）
└── integration/...                # 既有計費/零回歸

frontend/src/
├── components/api-usage-example.tsx   # 加 moderation/search/image_edit 範例（依 kind）
└── routes/catalog-detail.tsx          # kind 型別加 moderation/search/image_edit/image-edit
```

**Structure Decision**: web application。核心是 `proxy/` 內新增 `engine.py`（不變的執行流程）+ `endpoint_spec.py`（三軸抽象）+ `registry.py`（8 筆資料），刪除 5 個複製檔。串流端點 `router.py`/`responses.py` 保持獨立。計費/preflight 沿用既有 service，引擎只是把它們串起來一次。

## Complexity Tracking

> 無 Constitution 違反，無需填寫。串流端點排除為範圍決策（research R1）。
