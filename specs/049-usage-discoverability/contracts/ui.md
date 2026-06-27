# Contract: UI（無 API 契約變更）

本功能**不改任何後端 API**——重用既有 `/me/credentials`、`/catalog`。契約是 **UI 結構 + 元件 props + 資料 join**。

## 既有 API（沿用，不改）

| 端點 | 用到的欄位 |
|---|---|
| `GET /me/credentials` | `[].allocations[].{resource_model, display_name, status}`（這把金鑰 scope 的 model） |
| `GET /catalog`（成員可見） | `[].{slug, kind, display_name, responses_support.state}`（補 kind / responses） |

前端以 `slug == resource_model` join 兩者，得「金鑰可用 model + kind」。

## US1：金鑰頁「如何使用這把金鑰」

```
keys.tsx 每把金鑰卡：
  ── 區塊「如何使用這把金鑰」（顯眼、不需鑽詳情）
       ├─ model 下拉：options = 該金鑰 allocations 中 status=active 的 model
       │                （label = display_name，value = resource_model）
       ├─ 選中 model → <ApiUsageExample
       │                  model={slug}
       │                  kind={catalogKindOf(slug)}
       │                  supportsResponses={responsesOf(slug)}
       │                  isEmbedding={kind==='embedding'} isOcr={kind==='ocr'} />
       └─ scope 無可用 model → 提示（去領取 / 已被撤回），不渲染壞範例
  ── base URL + $TOKEN 佔位（不顯示真實 token）
```

**契約測試（vitest）**：
1. 金鑰有可用 model → 「如何使用這把金鑰」可見、下拉列該金鑰的 model、選了顯示範例（端點/slug 正確、token 為 `$TOKEN`）。
2. 一把金鑰多 model → 下拉列**全部**該金鑰 active model；切 model 換範例。
3. 兩把金鑰 → 各自下拉只列**自己 scope** 的 model（不混）。
4. 非 chat model（embedding/ocr）→ 範例對應正確端點（`/embeddings`、`/ocr`…）。
5. scope 空 → 顯示提示、無範例。

## US2：應用頁「直接用 API / SDK」卡

```
apps.tsx（註冊表驅動）→ 多一張 "直接用 API / SDK" tile
  /apps/api 詳情：model 下拉（成員可用 model）+ <ApiUsageExample/>
工具卡（Codex…）維持。
```

**契約測試**：應用頁同時有「工具整合」卡（≥1，Codex）與「直接用 API / SDK」卡；後者可選 model 並顯示範例。

## US3：cross-link

```
dashboard / member-overview（已有金鑰的待辦）→「開始呼叫 → 如何使用」連結
allocation-detail、catalog-detail → 既有 ApiUsageExample 保留 + 「想接工具 → 看應用」連結
```

**契約測試**：三處各有一個通往「如何使用 / 應用」的連結。

## 不洩漏 / 隔離

- 範例一律 `$TOKEN` 佔位，不顯示金鑰明文（金鑰 show-once 不變）。
- 成員只看自己的金鑰（`/me/credentials`）與成員可見 model（`/catalog`）——沿用既有隔離，無新資料路徑。
