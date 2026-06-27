# Phase 0 Research: 「如何呼叫」可發現性重設計

spec 無 `[NEEDS CLARIFICATION]`（下拉來源已定為方案 b）。本檔釘死實作層的資料來源與重用方式——全部對照既有程式，結論是**純前端、零後端**。

---

## R1：金鑰 scope 的「可用 model + kind + responses 能力」從哪取？（決定純前端 vs 動後端）

**Decision**：**純前端 join**——`/me/credentials`（已回每把金鑰的 `allocations[].{resource_model, display_name, status}`，即這把金鑰 scope 的 model）⋈ `/catalog`（已回每個 model 的 `kind` / `responses_support` / `display_name`），以 **model slug 為 key** 在前端合併。**不改任何後端端點 / schema。**

**Rationale**：
- `/me/credentials` 的 `AppCredentialOut.allocations`（`AllocationRef`）**已經是 (b) 要的「這把金鑰可用 model」清單**——含 slug + 顯示名稱 + 狀態，零後端改動就拿得到 scope。
- `ApiUsageExample` 需要 `kind`（+ `supportsResponses`/`isEmbedding`/`isOcr`）才能挑對端點範例；這些 **`/catalog` 成員端已暴露**（`api/catalog.py`：`"kind": model_kind(m)` + `responses_support`）。catalog-detail 正是這樣餵 `ApiUsageExample` 的。
- 故金鑰頁只要：拿 `/me/credentials`（scope）+ `/catalog`（kind/responses map），用 slug 對起來 → 餵 `ApiUsageExample`。兩個查詢都已是成員既有資料、TanStack Query 可快取。

**Alternatives considered**：
- 在 `AllocationRef` 加 `kind` + `supports_responses`（`/me/credentials` 自包含）→ 否決：要動後端序列化 + contract + 測試，但 `/catalog` 已有 kind，前端 join 一行 map 即可，**零後端更省**（YAGNI）。
- 新增「這把金鑰可用 model（含 kind）」專用端點 → 否決：既有兩端點已涵蓋，加端點違 YAGNI。

**邊界**：金鑰 scope 的某 model 若 `/catalog` 查無（orphan slug，catalog row 被移除）→ 前端 map 缺 kind → `ApiUsageExample` 以**預設對話/responses 範例**呈現（元件對「有 model、無 kind」本就退 chat）。可接受、需在元件確認此退路順。

---

## R2：呈現重用——`ApiUsageExample` 當單一來源

**Decision**：所有「呼叫範例」一律走既有共用元件 `ApiUsageExample`（props：`model` / `kind` / `supportsResponses` / `isEmbedding` / `isOcr`），**不複製任何 curl/Python/JS 文本**。金鑰頁＝一個 **model 下拉** + 一個 `ApiUsageExample`（依選中 model 的 kind 餵 props）。

**Rationale**：呼應 experience「同一概念的 UI 做兩份一定會 drift → 抽共用元件」+ 原則 5 集中管理。元件已支援所有端點型態（chat/responses/embedding/ocr/image/rerank/tts/stt/moderation/search/image_edit/realtime），選了 model 就對。

**Alternatives considered**：金鑰頁自己寫一段範例 → 否決：必 drift（正中那條教訓）。

---

## R3：US2 應用總站 + US3 cross-link 落點

**Decision**：
- **US2**：`lib/applications.tsx` 註冊表加一筆「**直接用 API / SDK**」（`id: "api"`，`Detail` 元件＝model 下拉 + `ApiUsageExample`）；`apps.tsx` 自動多一張 tile（註冊表驅動，原則 7「加一筆資料」）。下拉來源在應用頁是**成員可用 model**（`/catalog` 成員可見清單；非單把金鑰）。
- **US3**：cross-link 落三處——① 儀表板（`dashboard.tsx` / `member-overview.tsx` 的「有金鑰了」待辦/快速接入）加「開始呼叫 → 如何使用」；② `allocation-detail.tsx`、③ `catalog-detail.tsx` 既有 `ApiUsageExample` 保留，旁加「想接工具 → 看應用」連結。

**Rationale**：應用商店是註冊表（階段 27/28），加用法＝加資料；cross-link 補滿 scent（spec 的 FR-005/FR-007）。

**Alternatives considered**：把「直接 API」做成獨立頁而非應用卡 → 否決：應用頁本就是「怎麼用這個平台」的家，收斂在那符合原則 5（單一所在地）。

---

## 研究結論彙整（給 Phase 1 / tasks）

| 問題 | 結論 | 落地 |
|---|---|---|
| 金鑰 scope 的 model + kind | `/me/credentials`（scope）⋈ `/catalog`（kind），前端 join；**零後端** | `keys.tsx` |
| 範例呈現 | 重用 `ApiUsageExample`（單一來源） | `keys.tsx` / `apps.tsx` / 註冊表 |
| 應用總站 | 註冊表加「直接 API/SDK」一筆 | `lib/applications.tsx` + `apps.tsx` |
| cross-link | 儀表板 + 分配詳情 + 模型詳情 | `dashboard`/`allocation-detail`/`catalog-detail` |
| 後端 / migration | **不動** | — |
