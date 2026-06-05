# Research：憑證 UI 術語與層級收斂

## 1. 改名端點：併進既有 PATCH，不另開

- **Decision**：`Credential.name` 已存在，只需允許更新。在既有 `PATCH /me/credentials/{id}`（目前收 scope `add`/`remove`）與 admin `PATCH /admin/credentials/{id}` **多收選填 `name`**；提供 → 改名 + 寫稽核 `credential_renamed`。service 用既有 `get_credential` + set name（或 `patch_credential_scope` 接 `name`）。
- **Rationale**：YAGNI——一個欄位的標籤更新不值得專屬端點；同端點同時調 scope + name 也符合「編輯這把金鑰」的心智。改名不碰 token / scope → 零風險。
- **Alternatives**：① 專屬 `POST /me/credentials/{id}/rename` —— 多餘；② 放 PUT 整體覆寫 —— 過重、易誤刪 scope。

## 2. 分配詳情：降唯讀（不移除）

- **Decision**：分配（model）詳情頁以**唯讀**元件 `AllocationKeysReadonly` 取代可管理的 `DeviceCredentialsCard`。資料用既有 `GET /me/allocations/{id}/credentials`（回「scope 含此分配的金鑰」，每筆已含 `allocations` 全部 model 嗎？——Phase 18 該端點回 `CredentialOut`（單 prefix），**需確認/補**它回每把的全部可用 model）。若不足，改用成員層 `GET /me/credentials` 在前端 filter「scope 含此 allocation」即可（免動後端）。
- **Rationale**：使用者看某 model 時仍想知道「哪些金鑰能用它」；唯讀 + 顯示全部 model + 連本尊，正好消除無聲連坐。
- **Alternatives**：① 整個移除 —— 失去「哪些金鑰能用此 model」的實用資訊；② 保留可管理 —— 正是要消除的無聲連坐源。
- **實作取捨**：優先**前端用 `/me/credentials` 過濾**（資料最完整、含每把全部 model），免改後端；分配詳情頁本來就會抓成員資料。

## 3. admin 治理移到成員頁

- **Decision**：移除 `admin/allocations.tsx` 的「查看裝置憑證」dialog；在 `admin/member-detail.tsx` 加**唯讀應用金鑰清單 + 撤回 + 改名**，資料走 `GET /admin/members/{id}/credentials`、操作走 `DELETE`/`PATCH /admin/credentials/{id}`（階段 20 已有）。
- **Rationale**：金鑰屬成員（M:N 跨多分配），治理自然在成員層；per-allocation dialog 與無聲連坐同源，移除。
- **Alternatives**：保留 per-allocation admin dialog —— 與成員層重複、且連坐。

## 4. 術語統一「應用金鑰」

- **Decision**：全站把「裝置 / 憑證」對這個物件的稱呼改「**應用金鑰**」：`device-authorize.tsx`（「授權裝置」→「授權應用金鑰」/「授權這台裝置使用…」改寫）、`codex-install-card.tsx`（加「會在你的應用金鑰新增一把」）、分配詳情、admin 頁。device-flow 後端的 `device_authorizations` 表名 / API 路徑**不改**（內部名詞，使用者看不到）。
- **Rationale**：一物一名，原則 6 白話。內部 API/表名不動以免擴大風險。
- **Alternatives**：「API 金鑰」/「金鑰」—— 使用者已選「應用金鑰」（knowie-next 收斂）。

## 5. 退役 DeviceCredentialsCard

- **Decision**：`device-credentials-card.tsx` 的**管理**用途退役（member → `AllocationKeysReadonly`；admin dialog 移除）。元件可刪除或保留為唯讀基底；連帶 `credential-list.test.tsx` 改寫或移除。
- **Rationale**：其功能（per-allocation 新增/撤回/rotate）正是無聲連坐源 + 與成員層重複。
- **Risk/經驗**：移除舊卡前先確認能力已被承接（dashboard 金鑰卡 + admin 成員頁）——沿用「收尾 A 先安置再移除」的經驗。

## 未解項

- 無 `NEEDS CLARIFICATION`。需在實作時確認 `GET /me/allocations/{id}/credentials` 回的每筆是否含「全部可用 model」；不含則前端改用 `/me/credentials` 過濾（已定為優先做法，免動後端）。
