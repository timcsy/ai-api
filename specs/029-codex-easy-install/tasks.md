---
description: "Tasks for 階段 19 — 一鍵安裝 Codex + device-flow 免貼 token"
---

# 任務清單：成員一鍵安裝 Codex + device-flow 免貼 token

**輸入文件**：`/specs/029-codex-easy-install/` 下的
[plan.md](./plan.md) / [spec.md](./spec.md) / [research.md](./research.md) /
[data-model.md](./data-model.md) / [contracts/device-flow.openapi.yaml](./contracts/device-flow.openapi.yaml) /
[quickstart.md](./quickstart.md)

**測試（憲章 TDD）**：後端先寫失敗測試（Red）再實作（Green）。**最高優先固化**：
① device_code **時效/單次/節流** ② **擁有者邊界**（非擁有者/未登入不得核可、不 mint）
③ migration `0016` 後**既有 token/proxy/計費零回歸**。新表 migration **必在 Postgres 整合測試驗**。

**鐵則**：明文僅 Fernet 暫存、輪詢**單次交付即清**（hash-only 有界例外，FR-008/010）；mint 沿用階段 18
`add_credential`（憑證進「裝置與憑證」清單、可撤回/rotate，FR-013）；不改 Codex 上游協定（FR-016）。

**路徑慣例**：後端 `src/ai_api/`、`alembic/versions/`；測試 `tests/`；前端 `frontend/src/`；安裝腳本 `src/ai_api/install/`

---

## Phase 1：Setup

- [X] T001 跑基準綠（實作前對照）：`uv run pytest tests/ -q`、`uv run ruff check .`、`uv run mypy src/`、
      `npm --prefix frontend run test && lint && typecheck && build` 全綠；確認**不新增依賴**、下一個 migration 為 `0016`、
      既有 Fernet 基建（`PROVIDER_KEY_ENC_KEY`，`services/provider_credentials.py`）可復用於明文暫存。

---

## Phase 2：Foundational（阻斷性前置：device 表 + service 核心 + 零回歸）

**⚠️ 所有 device-flow user story 都依賴此資料模型與 service 核心；先做完。**

### Tests First (Red)

- [X] T002 新增 `tests/integration/test_device_migration.py`（Postgres）：跑 `alembic upgrade head` →
      斷言 `device_authorizations` 建出（unique `device_code`/`user_code`、FK、enum 存 VARCHAR、tz 欄）；
      且既有一筆 allocation 的舊 token 仍能 `lookup_by_token`（**零回歸**）。
- [X] T003 [P] 新增 `tests/contract/test_device_flow.py`（service 層先行部分）：`DeviceFlowService` 的
      `authorize` 產生唯一 device_code/user_code + 到期；`poll` 在 `pending`/`approved`/`expired`/`denied` 各回正確語意；
      過快 poll 回 `slow_down`（先全 Red）。
- [X] T004 跑 T002–T003 確認 **全 Red**。

### Implementation (Green)

- [X] T005 新增 `src/ai_api/models/device_authorization.py`：`DeviceAuthorization` ORM（欄位/索引/狀態 enum 依 data-model.md）；
      在 `models/__init__.py` 匯出。
- [X] T006 新增 `alembic/versions/0016_device_authorizations.py`：建 `device_authorizations`（unique device_code/user_code、
      FK→members/allocations/credentials、三索引）；**無循環 FK**；`downgrade` drop 表。
- [X] T007 新增 `src/ai_api/services/device_flow.py`：`DeviceFlowService`——
      `authorize(device_label) -> (device_code,user_code,expires_in,interval)`（高熵 device_code、`XXXX-XXXX` user_code、TTL 600s）；
      `get_pending(user_code)`；`approve(user_code, member, allocation_id)`（擁有者檢查→`AllocationService.add_credential`→Fernet 加密暫存明文→`approved`+稽核）；
      `deny(user_code, member)`；`poll(device_code)`（節流 `slow_down`、時效 `expired_token`、`access_denied`、成功回明文一次並清 `encrypted_token`）。
- [X] T008 在 `src/ai_api/models/auth_audit.py` 加 `device_authorization_approved` / `device_authorization_denied`
      兩個 `AuditEventType` 值（VARCHAR enum，免 migration）。
- [X] T009 跑 T002–T003 + 既有全套 `uv run pytest tests/` 確認 **全 Green、零回歸**。

**Checkpoint**：device 資料模型 + service 核心上線、既有零回歸。可進 US1。

---

## Phase 3：US1 — 一行指令裝好 + 瀏覽器一鍵授權（P1）🎯 MVP

**目標**：成員複製一行指令 → 瀏覽器授權選分配 → 腳本自動拿 per-device 憑證、跑通測試呼叫，全程不貼 token。

### Tests First (Red)

- [X] T010 [US1] 在 `tests/contract/test_device_flow.py` 加端點契約：`POST /device/authorize` 回
      device_code/user_code/verification_uri/expires_in/interval；未核可前 `POST /device/token` 回 `authorization_pending`，過快回 `slow_down`。
- [X] T011 [P] [US1] 新增 `tests/contract/test_device_owner_isolation.py`：未登入 `GET/approve /me/device/{code}` → 401；
      成員 approve **他人**分配 → 403、**不 mint**（憑證數不變）。
- [X] T012 [US1] 在 `tests/contract/test_device_flow.py` 加 happy path：擁有者 `approve {allocation_id}` → 204 →
      `POST /device/token` 回明文 token + credential_id **一次** → 該 token 可成功打 proxy → 再次 `POST /device/token` 回 `expired_token`（明文已清）。
- [X] T013 [US1] 跑 T010–T012 確認 **全 Red**。

### Implementation (Green)

- [X] T014 [US1] 新增 `src/ai_api/api/device.py`：公開 `POST /device/authorize`、`POST /device/token`（無 session，呼叫 `DeviceFlowService`）；
      於 `src/ai_api/main.py` `include_router`。
- [X] T015 [US1] 在 `src/ai_api/api/me.py` 加 `GET /me/device/{user_code}`、`POST /me/device/{user_code}/approve`（body `allocation_id`，
      `current_member` + 擁有者檢查、寫稽核）、`POST /me/device/{user_code}/deny`；schema 對齊 contract。
- [X] T016 [US1] 跑 T010–T012 確認 **全 Green**。
- [X] T017 [P] [US1] 前端：新增 `frontend/src/routes/device-authorize.tsx`（`/device` 路由，支援 `?code=` 預填）——
      `GET /me/device/{code}` 顯示摘要 → 選自己的分配（下拉）→ 核可/拒絕；非本人分配不可選；接進 router。
- [X] T018 [P] [US1] 前端 vitest：`frontend/src/__tests__/device-authorize.test.tsx` 驗摘要渲染 + 選分配 + approve/deny 呼叫；
      跑 lint/typecheck/build 綠。

**Checkpoint**：device-flow 後端 + 授權頁可用——「免貼 token 拿到憑證」端到端成立（安裝腳本於 US2/US3 補齊）。

---

## Phase 4：US2 — 安裝腳本：日常零參數零環境變數（P1）

**目標**：一行指令裝好 Codex、寫好設定與憑證，新終端機打 `codex` 零參數可用。

### Tests First (Red)

- [X] T019 [US2] 新增 `tests/contract/test_install_endpoint.py`：`GET /install/codex.sh`、`/install/codex.ps1` 回非空純文字、
      `Content-Type: text/plain`，內含平台 `base_url`、`model_providers.ccsh`、`wire_api = "responses"`、`requires_openai_auth`、
      `codex login --with-api-key` 等關鍵字（先 Red）。
- [X] T020 [US2] 跑 T019 確認 **全 Red**。

### Implementation (Green)

- [X] T021 [US2] 新增安裝腳本樣板 `src/ai_api/install/codex.sh.tmpl` 與 `src/ai_api/install/codex.ps1.tmpl`：
      偵測 OS/arch → 下載 Codex 獨立 binary（GitHub Releases）→ merge-style 寫 `~/.codex/config.toml`（自訂 provider `ccsh`）→
      跑 device-flow（呼叫 `/device/authorize`、印 user_code + 授權網址、輪詢 `/device/token`）→ `codex login --with-api-key` 寫 auth.json →
      跑一次測試呼叫印 ✓；失敗給白話訊息。**訊息以英文為主**（避免 `.bat`/PowerShell 中英混排亂碼）。
- [X] T022 [US2] 新增 `src/ai_api/api/install.py`：`GET /install/codex.sh`、`/install/codex.ps1`——讀樣板、注入 `settings.base_url`、
      回 `PlainTextResponse`；於 `main.py` `include_router`。
- [X] T023 [US2] 跑 T019 確認 **全 Green**。
- [X] T024 [P] [US2] 前端：新增 `frontend/src/components/codex-install-card.tsx`（依 OS 顯示一行指令 + 一鍵複製，
      `curl … | sh` / `irm … | iex`）；接進 `frontend/src/routes/dashboard.tsx`；360px 不溢出。
- [X] T025 [P] [US2] 前端 vitest：`frontend/src/__tests__/codex-install-card.test.tsx` 驗依 OS 切換指令 + 複製內容。

---

## Phase 5：US3 — 切 model 不脫鉤（P1）

**目標**：Codex 內切 model 後仍指向本平台（不打 api.openai.com），不靠唯讀/wrapper。

### Tests First (Red)

- [X] T026 [US3] 在 `tests/contract/test_install_endpoint.py` 加斷言：腳本/設定採 **merge-style** 且設 `model_provider = "ccsh"`
      為預設、含 `supports_websockets = false`；**不含**唯讀（chmod a-w / readonly）或 wrapper/alias 字樣（先 Red）。
- [X] T027 [US3] 跑 T026 確認 **Red**。

### Implementation (Green)

- [X] T028 [US3] 調整 `src/ai_api/install/codex.{sh,ps1}.tmpl`：確保寫入時設預設 `model_provider="ccsh"` + `supports_websockets=false`，
      且為 merge（保留使用者既有區塊、只覆蓋 `model_providers.ccsh` 與預設 provider 指向）。
- [X] T029 [US3] 跑 T026 確認 **Green**。

---

## Phase 6：US4 — 授權後憑證可見、可單獨撤回（P2）

**目標**：device-flow mint 的憑證在「裝置與憑證」清單可見、可單獨撤回/rotate，撤一把不連坐。

### Tests First (Red)

- [X] T030 [US4] 在 `tests/contract/test_device_flow.py` 加：device-flow 交付的憑證出現在
      `GET /me/allocations/{id}/credentials`（具裝置名、無明文）；`DELETE …/{cid}` 後該 token 打 proxy 被拒、同分配其他仍可用（先 Red）。
- [X] T031 [US4] 跑 T030 確認 **Red**。

### Implementation (Green)

- [X] T032 [US4] 確認 `DeviceFlowService.approve` 以 `AllocationService.add_credential(allocation, device_label or "Codex")` mint，
      使憑證自然進清單（多半零改動；若 `device_label` 缺省則給可辨識預設）；跑 T030 確認 **Green**。

---

## Phase 7：Polish 與跨領域

- [X] T033 跑 `uv run pytest tests/` 全套確認零回歸（device-flow + 既有 token/proxy/計費/配額 + migration，SC-007）。
- [X] T034 跑 `uv run ruff check . && uv run mypy src/` 零警告；`npm --prefix frontend run test && lint && typecheck && build` 綠。
- [ ] T035 **三平台真機驗收（SC-006）**：Windows / macOS / Linux 各跑 quickstart 真機清單——
      一行指令 → 瀏覽器授權 → 新終端機零參數 `codex` → `/model` 切換不脫鉤 → 清單可見可撤回。記錄結果。
      **含「已裝過 Codex」情境**（quickstart 新增段）：已裝 CLI（不重裝、保留設定、切預設 provider、可逆登入）、
      已裝編輯器擴充（與 CLI 共用 `~/.codex/`，支援度如實記錄）、ChatGPT App/網頁版（確認不適用、引導改用 CLI）。
- [X] T036 [P] 更新 `knowledge/vision.md` 階段 19 → ✅（填完成日、實際交付、連結 history）；roadmap/狀態同步；
      修掉殘留狀態行（342 行「階段 18、19 規劃中」）。
- [X] T037 [P] 在 `knowledge/history/completed-phases-detail.md` 追加「## 階段 19」詳情（device-flow 設計、0016、明文單次交付、三平台真機結論）；
      若有新教訓（如 `.bat` 編碼、Gatekeeper）補 `knowledge/experience.md`。
- [X] T038 commit + push + 開 PR；push 前 `ruff check .` + 前端 build；**特別檢視 migration 0016 與明文暫存清除路徑**；等 CI 全綠後 squash merge 到 main。
- [X] T039 main image build 綠後 `helm upgrade`（同既有指令 + `--set migrationJob.enabled=true` 套 0016 + 新 sha）；
      live 驗：`/device/authorize`、`/install/codex.sh` 可達；既有 proxy/計費零回歸。
- [ ] T040 收尾：刪除被取代的舊分支 `027-codex-easy-install`（本機 + remote）；vision/history/roadmap 一致；標記 tasks 全完成。

---

## 依賴與順序

```text
Phase 1 (Setup)
   ↓
Phase 2 (Foundational：device 表 + migration 0016 + service 核心 + 零回歸) ← 阻斷
   ↓
Phase 3 (US1 device-flow 端點 + 授權頁) ── MVP（免貼 token 拿憑證）
   ↓
Phase 4 (US2 安裝腳本：零參數)  ← 用到 US1 的 device-flow 端點
   ↓
Phase 5 (US3 不脫鉤)           ← 精修 US2 的腳本設定寫法
   │
Phase 6 (US4 憑證可見可撤回)    ← 依階段 18，幾乎零改動
   ↓
Phase 7 (Polish：全測 + 三平台真機 + 文件 + 部署含 migration)
```

**MVP**：Foundational + US1（device-flow 免貼 token 拿到可呼叫憑證）即首個價值；US2/US3 把「裝起來零參數、切 model 不壞」補齊；US4 收尾。

**[P] 並行機會**：T003（與 T002）；US1 的 T011/T017/T018；US2 的 T024/T025；Polish 的 T036/T037。

---

## 任務統計

| Phase | 任務數 | 含測試 |
|-------|------:|------:|
| 1 Setup | 1 | 0 |
| 2 Foundational | 8 | 3 |
| 3 US1（P1，MVP） | 9 | 4 |
| 4 US2（P1） | 7 | 2 |
| 5 US3（P1） | 4 | 2 |
| 6 US4（P2） | 3 | 2 |
| 7 Polish | 8 | 0 |
| **總計** | **40** | **13** |

---

## 格式檢核

- ✅ `- [ ] T###` 開頭、含 ID、描述、檔案路徑；Setup/Foundational/Polish 無 Story 標；US1–US4 含 `[US#]`
- ✅ 可並行標 `[P]`
- ✅ TDD：每段 Tests First → Red → 實作 → Green；最高優先固化 device 時效/單次/節流 + 擁有者邊界 + migration 零回歸；migration 在 Postgres 驗

---

## 下一步

跑 `/speckit.implement` 開始實作；每完成一筆把 `- [ ]` 改 `- [X]`。三平台真機（T035）需你本機配合。
