# Phase 1 資料模型：會員介面分頁化

**無新增資料實體。無 schema 變更、無 migration。** 本功能是純呈現層重組。

## 呈現層映射（既有資料 → 新頁面位置）

| 既有資料 / 端點（不變） | 既有元件 | 新位置 |
|---|---|---|
| `/me/usage`（摘要） | `UsageSummary` | 用量頁 `/usage`；摘要片段亦入總覽 `/dashboard` |
| `/me/usage?group_by=...`（圖表） | `MemberUsageCharts` | 用量頁 `/usage` |
| `/me/allocations` | 分配卡列（新抽 `allocation-list`） | 分配頁 `/allocations`；count 入總覽 |
| `/me/usage?group_by=allocation` | 分配卡配額條 | 分配頁 `/allocations` |
| `/me/claimable-models` | 可自助領取區 | 分配頁 `/allocations`；非空時入總覽待辦 |
| `/me/credentials` | `AppCredentialsCard` | 金鑰頁 `/keys`；count + 空狀態待辦入總覽 |
| `apiBaseUrl()` / `member.gateway_base_url` | API 端點卡（新抽 `api-endpoint-card`） | 金鑰頁 `/keys` |
| Codex 安裝 | `CodexInstallCard` | 金鑰頁 `/keys`；快速接入入總覽 |

## 狀態衍生（前端計算，無新端點）

- **活躍分配數** = `/me/allocations` 過濾 `status === "active"` 的長度。
- **活躍金鑰數** = `/me/credentials` 過濾 `status === "active"` 的長度。
- **待辦：建立金鑰** = `/me/credentials` 活躍數為 0。
- **待辦：去領取** = `/me/claimable-models` 含 `state === "claimable"`。

## 金鑰「編輯」合一（既有後端契約，不變）

- `PATCH /me/credentials/{id}` 已支援 `{ name?, add?: string[], remove?: string[] }` 同送（見 `tests/contract/test_credential_rename.py::test_rename_with_scope_change_together`）。前端只把兩個 dialog 併成一個，送單一 PATCH。**後端零改動。**
