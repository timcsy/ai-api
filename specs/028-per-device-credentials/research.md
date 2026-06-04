# Research：憑證模型重構（每分配多 per-device 憑證）

spec 無殘留 NEEDS CLARIFICATION（取捨已於前置討論拍板）。以下為實作前技術決策。

---

## R1：`Credential` schema 1:1 → 1:N

- **Decision**：
  - 主鍵從 `allocation_id` 改為新的獨立 `id`（ULID，String(26)）。
  - `allocation_id` 改為**一般 FK + 索引（非唯一）**（一分配可多筆）。
  - 新增 `name: str`（裝置名 / label）、`last_used_at: datetime | None`、`revoked_at: datetime | None`（軟撤回）。
  - 保留 `token_fingerprint`（**仍唯一**）、`token_prefix`、`created_at`。
  - `Allocation.credential`（scalar）→ `Allocation.credentials`（list）。
- **Rationale**：對齊原則 1（唯一性在分配層、可多把獨立憑證）。fingerprint 唯一確保 token→credential 仍 1 對 1 命中。
- **Alternatives**：另開 `Device` 表 + Credential 綁 Device → 多一層 entity，無 metadata 需求，違反「M:N 不一定先建 entity」教訓。否決。

## R2：token 驗證零回歸（auth-critical）

- **Decision**：`lookup_by_token(plaintext)` 僅多一個過濾：`WHERE token_fingerprint == fp AND revoked_at IS NULL`。
  fingerprint 唯一 → 至多 1 把命中 → 回其 allocation。既有呼叫路徑（`preflight`、`auth`）與計費歸戶（`allocation_id`）**完全不變**。
- **Rationale**：把改動壓到最小、auth 路徑風險最低。既有 token 的 fingerprint 不變（migration 不重算）→ 舊 token 照解析。
- **驗證**：先寫測試固定「既有 token 仍解析、撤回後解析不到」。

## R3：撤回 = 軟撤回（`revoked_at`），保留稽核

- **Decision**：撤回某把 = 設 `revoked_at = now`（不刪列）；lookup 排除已撤回者 → 立即失效。撤回**留稽核事件**（沿用既有 audit）。
- **Rationale**：保留歷史/可稽核（誰、何時、撤哪把）；符合原則 2 與「拒絕路徑要有審計」既有教訓。硬刪會丟失軌跡。
- **Alternatives**：硬 DELETE → token 立即失效但無軌跡。否決。

## R4：rotate 再定義 + add/revoke API

- **Decision**：
  - 新增 service：`add_credential(allocation, name) -> token`（show-once）、`revoke_credential(credential_id)`、`list_credentials(allocation)`。
  - 既有 `rotate_token(allocation_id)`（原地換唯一一把）改為**相容語意**：對「最後一把/指定一把」做「撤舊+發新」，或前端改用 add/revoke。
    既有 member 端點 `/me/allocations/{id}/rotate-token` 保留（避免破壞既有 UI），內部映射到新模型。
  - 建立分配（admin + 自助領取）時建**第一把**具名憑證（如 `name="預設"`）。
- **Rationale**：複用既有流程、最小破壞；「下放 admin 能力 = 同一 service + 端點層擁有者檢查」既有教訓。
- **追 sink**（呼應「加欄位要追所有讀寫顯示點」）：`services/allocations.py`、`api/{me,allocations,schemas}.py`、
  `proxy/preflight.py`、`services/self_service.py`、前端分配詳情/dashboard 顯示 token_prefix 處——逐一適配 1:N。

## R5：Migration 0015（保留既有資料、Postgres 必驗）

- **Decision**：Alembic `0015`，用 **`batch_alter_table`**（SQLite 改主鍵需重建表；Postgres 亦相容）：
  - 重建 `credentials`：`id` PK、`allocation_id` 一般 FK+索引、加 `name`/`last_used_at`/`revoked_at`、`token_fingerprint` 唯一。
  - **資料保留**：既有每列 → 補 `id`（新 ULID）+ `name="預設"`，**token_fingerprint/prefix 原樣搬**（→ 既有 token 不失效）。
- **Rationale**：「本機 SQLite 寬鬆、Postgres 嚴格——結構變更要用 Postgres 驗一次」既有教訓 → integration 測試 seed 舊式資料、跑 migration、驗舊 token 仍解析。
- **Alternatives**：新表 + 雙寫過渡 → 過度工程，資料量小。否決。

## R6：`last_used_at` 更新節流

- **Decision**：成功驗證時更新 `last_used_at`，但**節流**——僅當距上次 > 例如 5 分鐘才寫，避免每次 proxy 呼叫寫 DB。
- **Rationale**：避免 auth 熱路徑寫放大；`last_used_at` 只為清單顯示，分鐘級精度足夠。
- **Alternatives**：每次都寫（寫放大）/ 完全不記（FR-008 要顯示）。折中採節流。

## R7：前端 — 「裝置/憑證」清單 + 遮罩複製面板

- **Decision**：member 在分配詳情/dashboard 看「我的裝置」清單（add/list/revoke）；admin 在分配詳情看某成員所有憑證可撤。
  新增裝置時用先前設計的**遮罩 + 一鍵複製**面板顯示一次（沿用階段 16 RWD：base grid、min-w-0）。
- **Rationale**：「backend 有 API 沒 UI = 功能未完成」既有教訓。複用既有元件、零新依賴。

## R8：測試分工

- contract：`/me/allocations/{id}/credentials` add/list/revoke（owner-scoped、他人操作 403）；admin 端點。
- integration（Postgres）：`test_credential_migration`——seed 舊式單憑證 → migration → 舊 token 仍解析；多憑證並存；撤一把不連坐。
- 既有 token 驗證/計費/領取的回歸：跑全套確認零退化。

---

## 小結

- 改動集中在 `credentials` 表 + service + 端點 + 一個 migration；auth 路徑改動極小（加 `revoked_at IS NULL`）。
- 既有 token 零回歸是先寫的測試重點；migration 必在 Postgres 驗。
- 無新依賴、無 device-flow（階段 19）、無數量上限。
