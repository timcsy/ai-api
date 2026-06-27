# Phase 1 Data Model: 「如何呼叫」可發現性重設計

**核心結論：無持久化實體、無 schema 變更、無 migration。** 本功能是呈現層重排 + 既有資料前端 join；以下是**呈現用的衍生視圖**（非資料表）。

## 1. 金鑰可用 model 視圖（前端衍生，US1）

每把金鑰「如何使用」下拉的一個選項：

| 欄位 | 來源 | 說明 |
|---|---|---|
| `model_slug` | `/me/credentials` → `allocations[].resource_model` | 這把金鑰可用的 model（scope）；也是範例填入的識別字 |
| `display_name` | `/me/credentials` → `allocations[].display_name`（或 `/catalog` 補） | 下拉顯示的可讀名稱 |
| `kind` | `/catalog`（slug ⋈）→ `kind` | 決定 `ApiUsageExample` 餵哪種範例（chat/embedding/ocr/realtime…）；查無 → 退 chat |
| `supports_responses` | `/catalog`（slug ⋈）→ `responses_support.state == "available"` | 餵 `ApiUsageExample` 的 `supportsResponses` |

**取得方式**：`/me/credentials`（scope）+ `/catalog`（kind/responses map），前端以 `model_slug` join。**只列 `status == active` 的 scope model**；空集合 → 顯示提示（FR-009）。

## 2. 範例呈現（既有共用元件，不新增）

`ApiUsageExample`（既有）props：`model`、`kind`、`supportsResponses`、`isEmbedding`(=`kind==='embedding'`)、`isOcr`(=`kind==='ocr'`)。**單一來源、各處重用**（US1/US2/US3 與既有詳情頁共用同一元件）。

## 3. 應用註冊表項（既有結構，加一筆，US2）

`lib/applications.tsx` 的 `Application`（既有：`id` / `name` / `blurb` / `Logo` / `Detail`）新增一筆：

| 欄位 | 值 |
|---|---|
| `id` | `"api"` |
| `name` | 「直接用 API / SDK」 |
| `blurb` | 一句白話（自己寫程式怎麼接） |
| `Logo` | 通用 API/code 圖示 |
| `Detail` | model 下拉（成員可用 model）+ `ApiUsageExample` |

**加用法＝加一筆資料**（原則 7 註冊表），`apps.tsx` 自動多一張 tile + 詳情。

---

**結論**：**無資料表、無欄位、無 migration、無新端點**。資料來自既有 `/me/credentials` + `/catalog`；呈現重用 `ApiUsageExample`；應用以既有註冊表加一筆。
