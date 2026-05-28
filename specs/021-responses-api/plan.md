# Implementation Plan: Responses API / Agent 工具（Codex）相容

**Branch**: `021-responses-api` | **Date**: 2026-05-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/021-responses-api/spec.md`

## Summary

開放 OpenAI Responses API 相容的 `POST /v1/responses` 端點，讓 Codex 等 agent CLI
以平台憑證即可使用。技術取向（見 [research.md](./research.md)）：**統一以
`litellm.aresponses()` 路由所有 provider**（OpenAI/Azure 高保真、其他自動橋接），
支援 SSE streaming、tool calls、推理；與 `/chat/completions` **共用**前置 pipeline；
精確分項計費（reasoning / cached token，含 migration）；自建 `stored_responses`
映射表做 `store` / `previous_response_id` 的歸屬隔離。

## Technical Context

**Language/Version**: Python 3.11+（後端）/ TypeScript strict（前端僅用量顯示微調）
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Pydantic v2、`litellm`
（library form，`aresponses`）、Alembic、`httpx`（litellm 內含）；皆既有，不新增套件
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；migration `0013_responses_api`
（`call_records` +2 欄、`price_list` +1 欄、新表 `stored_responses`）
**Testing**: pytest——新測試優先 Docker-free（temp-file / in-memory SQLite）；
migration 與 PG 專屬行為走 Postgres 整合測試（CI 已涵蓋）
**Target Platform**: Linux server（Kubernetes；frontend nginx 反向代理 + Traefik ingress）
**Project Type**: web-service（gateway）+ 少量 frontend（用量分項顯示）
**Performance Goals**: 串流首位元組低延遲、端到端不緩衝；無新增吞吐目標
**Constraints**: provider key 絕不外洩（原則 1）、每次呼叫歸戶（原則 2）、撤回即拒
（原則 3）、TDD + 契約優先（憲章 I/II）
**Scale/Scope**: 組織內部；單一新端點 + 共用 pipeline 重構 + 1 migration + 1 新表

## Constitution Check

*GATE: Phase 0 前須過；Phase 1 後重檢。*

| 原則 | 評估 | 結論 |
|------|------|------|
| I. Test-First | tasks 將以「契約測試 / 整合測試先行（Red）→ 實作（Green）→ 重構」排序；重構既有 `/chat/completions` 有既有測試為安全網 | ✅ 計畫遵守 |
| II. Contract-First | 已先寫 [contracts/responses.md](./contracts/responses.md)，實作前過審 | ✅ |
| III. 整合測試覆蓋外部依賴 | litellm/Azure 邊界 + DB migration 以整合測試（Postgres）驗證；SSE 以 mock 上游 + 真機 Codex 收尾 | ✅ |
| IV. 可觀測性 | 沿用結構化日誌 + request_id；錯誤帶 code；負向測試驗證無 key 外洩 | ✅ |
| V. YAGNI | **統一 litellm**（而非混合 pass-through）即為 YAGNI 抉擇；新欄位/新表皆由明確需求驅動（精確計費、歸屬隔離） | ✅ 無違反 |

**初檢結果**：PASS，無 Complexity Tracking 需填。
**Phase 1 後重檢**：設計（contracts/data-model）未引入額外抽象或旗標，維持 PASS。

## Project Structure

### Documentation (this feature)

```text
specs/021-responses-api/
├── plan.md              # 本檔
├── research.md          # Phase 0：7 項技術決策
├── data-model.md        # Phase 1：migration 0013 + 新表
├── quickstart.md        # Phase 1：Codex 連線驗證
├── contracts/
│   └── responses.md     # Phase 1：/v1/responses 契約
├── checklists/
│   └── requirements.md  # spec 品質清單（已過）
└── tasks.md             # Phase 2（/speckit.tasks 產生，本指令不建）
```

### Source Code (repository root)

```text
src/ai_api/
├── proxy/
│   ├── preflight.py     # 新增：抽出的共用前置 pipeline（bearer→alloc→quota→binding→access→credential）
│   ├── router.py        # 改：/chat/completions 改用 preflight（行為保持）
│   ├── responses.py     # 新增：POST /v1/responses（請求驗證 + preflight + 串流轉發 + usage 擷取）
│   └── upstream.py      # 改：加 aresponses() 包裝（litellm，stream 支援）
├── models/
│   ├── call_record.py   # 改：+reasoning_tokens, +cached_tokens
│   ├── price_list.py    # 改：+cached_input_per_1k_tokens_usd
│   └── stored_response.py  # 新增：stored_responses 映射表
├── services/
│   ├── pricing.py       # 改：calculate_cost 納入 cached 折扣（reasoning 已含 output）
│   ├── records.py       # 改：record_call 接受 reasoning_tokens/cached_tokens
│   ├── usage.py         # 改：aggregate_usage 可選加總新分項
│   └── stored_responses.py  # 新增：store 寫入 / previous_response_id 歸屬查驗 / TTL 清理
└── api/
    └── catalog/...      # 模型 capabilities "responses" 載入（YAML 補標記）

alembic/versions/
└── 0013_responses_api.py  # 新增 migration

deploy/
├── catalog/*.yaml       # 改：支援模型補 responses capability
├── nginx/default.conf.template  # 改：/v1/responses proxy_buffering off
└── helm/ai-api/templates/...    # 改：ingress SSE 不緩衝（必要時）+ stored_responses 清理 cronjob

frontend/src/...         # 改：用量顯示分項（reasoning/cached，小幅）

tests/
├── contract/test_responses.py          # 新增：契約（前置拒絕、capability、歸屬隔離、無 key 外洩）
├── integration/test_responses_stream.py # 新增：SSE mock 上游 + 斷線記用量
├── integration/test_responses_billing.py# 新增：reasoning/cached 分項計費
├── integration/test_stored_responses.py # 新增：store/previous_response_id + 歸屬隔離 + TTL
└── integration/test_migration_0013.py   # 新增：PG migration 前滾/後滾
```

**Structure Decision**: 沿用既有單一後端 `src/ai_api/` 結構（web-service）。新端點與
共用 pipeline 置於既有 `proxy/` 套件；資料層擴充既有 `models/` + 一張新表；計費/記錄/
用量沿用既有 `services/`。前端僅用量分項顯示微調。符合既有專案佈局，無新頂層模組。

## 實作階段建議（供 /speckit.tasks 展開）

1. **資料層先行**：migration 0013 + model 變更 + 失敗測試（schema / migration PG）。
2. **共用 pipeline 抽出**：`preflight.py` + 把 `/chat/completions` 切過去（既有測試需全綠＝行為保持）。
3. **計費擴充**：`calculate_cost` cached 折扣 + `record_call` 新參數 + 單元測試。
4. **/v1/responses 非串流**：端點 + preflight + capability gate + usage 對應 + 契約測試。
5. **streaming**：SSE 轉發 + 終局 usage 擷取 + 斷線記用量 + 整合測試（mock 上游）。
6. **多 provider**：litellm 橋接路徑驗證（Azure 保真 + 其他橋接）。
7. **server-side 狀態**：`stored_responses` 表 + store 寫入 + previous_response_id 歸屬查驗 + TTL 清理 + 隔離測試。
8. **部署**：nginx/ingress SSE 不緩衝 + 清理 cronjob。
9. **驗證**：Codex 真機（quickstart）+ 全測試綠 + 負向 key 外洩測試。

## 風險與緩解（自 spec / 經驗）

| 風險 | 緩解 |
|------|------|
| litellm 對 Codex 某欄位失真（如加密 reasoning） | 真機 Codex 驗證為驗收門檻；fallback：僅對 Azure 加狙擊式 raw pass-through（research R1） |
| SSE 被中介緩衝 → 502/timeout | nginx/ingress 不緩衝 + `curl -N` 與真機驗證（經驗「部署完成≠跑得起來」） |
| 串流中計費時序（usage 僅終局） | tee `response.completed`；斷線走 `finally` 記用量（FR-017） |
| 重構 `/chat/completions` 破壞既有行為 | 既有測試為安全網；先重構後上新端點 |
| PG migration 踩 tz/enum/index 坑 | nullable 欄位 + PG 整合測試 + Postgres-safe migration（經驗） |
| 歸屬隔離漏洞 | `stored_responses` 強制 allocation 比對 + 專門隔離測試（FR-015 / SC-004） |

## Phase 2 注意

本指令止於 Phase 1。`tasks.md` 由 `/speckit.tasks` 產生，須遵守 TDD 排序
（每項實作前有先行失敗測試）。
