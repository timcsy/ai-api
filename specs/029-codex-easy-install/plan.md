# Implementation Plan: 成員一鍵安裝 Codex + device-flow 免貼 token

**Branch**: `029-codex-easy-install` | **Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/029-codex-easy-install/spec.md`

## Summary

讓非技術成員「複製一行指令 + 在瀏覽器按一次授權」就裝好 Codex、零參數零環境變數使用、切 model 不脫鉤，**全程不複製貼上 token**。技術路徑：(1) 平台提供跨 OS 安裝腳本（抓 Codex 獨立 binary、merge-style 寫 `config.toml` 的自訂 provider `ccsh`、`codex login --with-api-key` 寫 `auth.json`）；(2) **device-flow（RFC 8628 改寫）**——腳本 `POST /device/authorize` 拿 `device_code`/`user_code` → 成員在已登入 dashboard `/device` 選分配並核可 → 平台 mint 一把 per-device 憑證（階段 18 模型）並把明文**暫存加密**於授權請求列 → 腳本 `POST /device/token` 輪詢一次取回明文後即清除。憑證落在既有「裝置與憑證」清單，可單獨撤回/rotate。

## Technical Context

**Language/Version**: Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端）/ POSIX `sh` + Windows PowerShell（安裝腳本）
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2、`cryptography`（Fernet，既有）、TanStack Query、shadcn/ui（**皆既有，不新增套件**）；安裝腳本下載 OpenAI Codex CLI 獨立 binary（GitHub Releases，client-side）
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**新表 `device_authorizations` + migration `0016`**
**Testing**: pytest（contract + integration，含 Postgres 跑 migration）、vitest（前端）、**三平台真機驗收**（Windows/macOS/Linux，腳本無法在 CI 全自動）
**Target Platform**: 後端 Linux/K8s；安裝腳本目標 Windows + macOS + Linux 成員機器
**Project Type**: web（既有 backend `src/ai_api/` + frontend `frontend/`）
**Performance Goals**: device-flow 輪詢間隔 ≥5s、授權時效 ~10 分鐘；不影響既有 proxy 熱路徑
**Constraints**: token 仍 show-once + hash-only（device-flow 的明文暫存為**加密、單次交付、交付即清**的有界例外）；不改 Codex 上游 Responses 協定；後端不需新增對外 egress
**Scale/Scope**: 後端 +1 表 +1 router（device）+ service；前端 +1 授權頁 +1 安裝區塊；3 份安裝腳本

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First（不可妥協）**：✅ device service / 端點先寫失敗 contract + integration 測試再實作。最高優先固化：① device_code 時效/單次/節流 ② 擁有者邊界（非擁有者/未登入不得核可）③ migration 後既有 token 零回歸。
- **II. 契約優先**：✅ `contracts/device-flow.openapi.yaml` 定義 `/device/authorize`、`/device/token`、`/me/device/{user_code}`（GET/approve/deny）；契約測試為合併前關卡。
- **III. 整合測試覆蓋外部依賴**：✅ 新表 migration `0016` **在 Postgres 整合測試驗**（經驗鐵則）；device-flow 全流程（authorize→approve→token 取回→撤回）整合測試。
- **IV. 可觀測性**：✅ 授權核可/拒絕/逾時留稽核（`device_authorization_*` event types，VARCHAR enum 不需 migration）。
- **V. 簡潔優先（YAGNI）**：✅ 不引入完整 OAuth server；以既有 session 為「已認證」來源；明文暫存復用既有 Fernet 基建（不新增金鑰機制）；安裝腳本為純 shell/PowerShell，不另造框架。

**結論：無違規，無 Complexity Tracking 需求。**

## Project Structure

### Documentation (this feature)

```text
specs/029-codex-easy-install/
├── plan.md              # 本檔
├── research.md          # Phase 0：device-flow 設計、Codex 設定真機結論、明文交付策略
├── data-model.md        # Phase 1：device_authorizations 表 + 狀態機
├── quickstart.md        # Phase 1：驗收腳本（含三平台真機清單）
├── contracts/
│   └── device-flow.openapi.yaml
└── tasks.md             # /speckit.tasks 產出（本指令不建）
```

### Source Code (repository root)

```text
src/ai_api/
├── models/
│   └── device_authorization.py     # 新：DeviceAuthorization ORM
├── services/
│   └── device_flow.py              # 新：authorize / poll(token) / approve / deny / 過期清理；mint 憑證復用 AllocationService.add_credential
├── api/
│   ├── device.py                   # 新：公開 /device/authorize、/device/token（無 session）
│   └── me.py                       # 改：加 /me/device/{user_code} GET、approve、deny（current_member）
├── install/
│   └── (templates)                 # 新：codex 安裝腳本樣板（sh / ps1），由端點注入 base_url 回傳
└── api/install.py                  # 新：GET /install/codex.{sh,ps1}（PlainText，注入平台 base_url）

alembic/versions/
└── 0016_device_authorizations.py  # 新表

frontend/src/
├── routes/
│   └── device-authorize.tsx        # 新：/device 授權頁（輸入/確認 user_code → 選分配 → 核可/拒絕）
├── components/
│   └── codex-install-card.tsx      # 新：dashboard「安裝 Codex」一行指令（依 OS）
└── routes/dashboard.tsx            # 改：掛入安裝區塊

tests/
├── contract/
│   ├── test_device_flow.py         # authorize→pending→approve→token 取回一次；時效/節流/單次
│   └── test_device_owner_isolation.py  # 非擁有者/未登入不得核可；綁他人分配 403
└── integration/
    └── test_device_migration.py    # Postgres：0016 建表 + 全流程 + 既有 token 零回歸
```

**Structure Decision**: 沿用既有 web 結構（`src/ai_api/{models,services,api}` + `frontend/src` + `alembic` + `tests`）。device-flow 公開端點獨立成 `api/device.py`（無 session，給 CLI 輪詢）；核可端點放 `api/me.py`（既有 `current_member` + 擁有者把關）。安裝腳本以端點動態注入 `base_url` 回傳純文字，避免在前端硬編平台網址。

## Complexity Tracking

> 無違規，免填。
