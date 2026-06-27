# Data Model: OpenAI 相容 `/v1/models` ＋ Copilot 上卡

**無新增持久化實體、無 schema 變更、無 migration。** `/v1/models` 為唯讀投影；下列為對外 DTO 與其來源映射，及涉及的既有表（皆唯讀）。

## 對外 DTO（OpenAI 相容）

### `OpenAIModel`（單一模型物件）

| 欄位 | 型別 | 來源 | 說明 |
|------|------|------|------|
| `id` | string | `Allocation.resource_model` | 正規 slug（含 provider 前綴），＝呼叫時的 `model`、preflight 路由鍵（R2） |
| `object` | string 常數 `"model"` | — | OpenAI 慣例 |
| `created` | int（unix 秒） | `ModelCatalog.created_at`（查無則 `Allocation.created_at`）的 epoch | 慣例欄位、穩定即可（R3） |
| `owned_by` | string | `parse_provider(resource_model)` | provider（`azure`/`openai`/`anthropic`/`gemini`…） |

### `OpenAIModelList`（list 回應）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `object` | string 常數 `"list"` | OpenAI 慣例 |
| `data` | `OpenAIModel[]` | 金鑰 scope 內 active 分配的模型，依 `id` 排序；金鑰內 `UNIQUE(credential_id, resource_model)` 保證不重複 |

## 來源映射與規則

```
Bearer token
  └─ lookup_credential_by_token(token) ──► Credential（revoked_at IS NULL，否則 401）
       └─ list_active_scope_allocations(credential)
            = Allocation JOIN CredentialAllocation
              WHERE credential_id = :cid AND Allocation.status = 'active'
            ──► [Allocation...] ──map──► [OpenAIModel(id=resource_model, owned_by=provider, ...)]
```

- **過濾**：只含 `Allocation.status == active`（排除 `paused`/`revoked`/`quarantined`，FR-006）。
- **不套** catalog 存取政策 / pricing（R1）——分配存在即授權；未定價模型仍列出（FR-007）。
- **retrieve**：`resolve_scope_allocation(credential, id)`（exact + 唯一 bare alias），命中且 active → 該物件；否則 404（不洩漏 scope 外存在性）。

## 涉及的既有表（唯讀，無變更）

| 表 | 用途 |
|----|------|
| `credentials` | 金鑰本體；`token_fingerprint` 查詢、`revoked_at` 過濾、`last_used_at` 節流更新（既有行為） |
| `credential_allocations` | 金鑰 ↔ 分配 M:N（join）；`resource_model` 去重保證 |
| `allocations` | 取 `resource_model`、`status`、`created_at`、`member_id` |
| `model_catalog` | （可選）取 `created_at` 充 `created` 欄；不影響可發現性 |

## 應用卡（前端，非後端資料模型）

`frontend/src/lib/applications.tsx` 註冊表新增一筆：

| 欄位 | 值 |
|------|-----|
| `id` | `"copilot"` |
| `name` | `"GitHub Copilot"` |
| `Logo` | `CopilotLogo`（`app-logos.tsx` inline SVG） |
| `Detail` | `CopilotAppDetail`（設定步驟 + 建金鑰捷徑 + 跨 model 開新對話說明） |

承載於既有註冊表機制（原則 7：加一筆＝一張卡 + 一詳情），無資料庫變更。
