# Phase 0 — Research

## R1：11 → 6 入口的映射

**Decision**：

| 既有頁 | 新位置 |
|---|---|
| 首頁 | **首頁**（保留；增強 dashboard 模式）|
| 成員 | **成員**（強化為含 inline tag / member-detail / 該成員可用 model）|
| 分配 | 併入「成員」detail；URL `/admin/allocations` 保留為 redirect |
| Provider 憑證 | **Provider 憑證**（保留）|
| Tag | **Tag**（強化為含 detail 頁）|
| Model 存取 | 併入「**Model**」detail |
| Catalog 管理 | 併入「**Model**」list |
| 目錄（檢視）| 砍掉；admin 視角去 Model；member 視角直接看 `/catalog` |
| 用量 | 併入「**觀測**」之 tab |
| 配額池 | 同上 |
| Rebalance 記錄 | 同上 |
| 稽核紀錄 | 同上 |

**結果**：sub-nav 從 11 條 → **6 條**：首頁、Model、成員、Tag、Provider 憑證、觀測

**Rationale**：
- 「Model」是最高頻概念，三個既有頁拆得太散
- 「成員」+ 「分配」本來就是同概念延伸
- 觀測類四頁瀏覽流類似（看圖表、看 log），合 tab 自然
- 不動 Provider 憑證（已經內聚良好）

**Alternatives considered**：
- 砍到 5 條（把 Provider 憑證併入「設定」群組）：增加深度反而難找
- 留 7 條（觀測類拆 2 個 tab 群）：未達 SC-004 目標

## R2：deep-link 向後相容

**Decision**：用 React Router 在 `frontend/src/lib/legacy-redirects.tsx` 集中定義舊 → 新映射，掛在 App.tsx 的最後（在 NotFound 之前）。

```typescript
const LEGACY_REDIRECTS: Record<string, string> = {
  "/admin/catalog-manage": "/admin/model",
  "/admin/model-access": "/admin/model",
  "/admin/catalog": "/admin/model",
  "/admin/allocations": "/admin/member",
  "/admin/tags": "/admin/tag",
  "/admin/usage": "/admin/observability?tab=usage",
  "/admin/quota-pool": "/admin/observability?tab=quota",
  "/admin/rebalance-log": "/admin/observability?tab=rebalance",
  "/admin/audit": "/admin/observability?tab=audit",
};
```

**Rationale**：
- 純 client-side redirect，不動後端
- 集中在一個檔案，未來 nav 改動只動這裡
- 維持 `?tab=` 帶入，觀測 tab 直跳目標

## R3：「觀測」用 Tabs 還是 Sub-routes

**Decision**：用 React Router 的 sub-route，**不**用 shadcn Tabs：`/admin/observability/usage`、`.../quota`、`.../rebalance`、`.../audit`，外層 layout 渲染 tab bar。

**Rationale**：
- 每個子頁有獨立 URL → 可分享、可 deep-link
- 既有頁面（usage.tsx 等）內容可直接 `<Outlet />` 進來，無須重寫
- Tabs 元件適合「同一頁切視角」，這裡是 4 個完全獨立功能

## R4：「以 X 視角預覽可見性」函式

**Decision**：純函式 `evaluate_visibility(member, model, provider_creds) -> {visible, reason_chain}`，後端新 endpoint 包裝。前端使用 component `VisibilityDiagnose` 可嵌入 model detail / member detail / 通用診斷頁。

**Reason chain 範例**：

```json
{
  "visible": false,
  "reason_chain": [
    {"check": "credential_gate", "pass": true, "detail": "azure has 1 active credential"},
    {"check": "default_access", "result": "restricted"},
    {"check": "deny_tags", "pass": true, "detail": "member tags ∩ denied = ∅"},
    {"check": "allow_tags", "pass": false, "detail": "member tags ['eng'] ∩ allowed ['vip'] = ∅"}
  ]
}
```

**Rationale**：
- 直接重用既有 `access_policy_allows` 邏輯（services/model_access.py），不做 logic duplication
- reason chain 是 ordered list，前端按順序高亮失敗點 + 給「修補」按鈕（如果失敗於 allow_tags，按「加 X tag 給該 member」）

**Alternatives considered**：
- 只回 `{visible: bool}`：不符 FR-009 / FR-011（需 reason + 修補捷徑）
- 包裝成 service function 直接前端 import：違反前後端契約優先原則

## R5：首頁 onboarding → dashboard 切換邏輯

**Decision**：條件 = `provider_count > 0 && model_count > 0 && member_count > 0 && allocation_count > 0`。全部 >0 切 dashboard 模式（顯示用量摘要 / 最近異常 / audit 高亮）；任一 = 0 顯示 onboarding（既有 checklist UI）。

**Rationale**：
- Onboarding 是「初始狀態」，全配齊後不該再佔位
- 從 dashboard 退回 onboarding 不需特殊處理（自動重算）

## R6：Model detail 頁的內容組織

**Decision**：單頁三大區塊（卡片）：

1. **基本資訊** — display_name / provider / cost / context_window / description 等（既有 catalog-manage create form 內容）
2. **存取規則** — default_access + allowed/denied tags + 即時 preview（既有 model-access 內容）
3. **健康診斷** — provider credential 狀態 / N 個 member 可見 / K 個 allocation 綁定 / 嵌入「以 X 視角預覽」面板

**Rationale**：
- 一頁解決所有 model 相關問題，不必跨頁
- 健康診斷區塊把所有「為何隱藏 / 為何呼叫失敗」的入口收斂

## R7：Member detail 頁的內容組織

**Decision**：單頁四大區塊：

1. **基本資訊 + 操作** — email / provider / 狀態 / is_admin（既有 members 內容）
2. **Tag** — inline editable（已有 MemberTagsCell）+ link 到每個 tag 詳情
3. **可用 model** — 計算「該 member 在 catalog 可看到的 model 清單」
4. **Allocations** — 該 member 的 allocation 列表 + 「建分配」內嵌按鈕（既有 allocations create dialog）

**Rationale**：
- 把 admin 在 member 上會做的所有事收一頁
- 「可用 model」是新計算，重用 R4 函式 over all models

## R8：保留舊 admin 頁面檔案 vs 刪除

**Decision**：保留檔案，從 App.tsx route 移除，內容供 detail 頁複用為元件。例 `tags.tsx` 內的批次貼標 dialog → 抽成 `BulkApplyTagDialog` component。

**Rationale**：
- 漸進式重組；萬一有遺漏可快速 revert nav
- 元件提取可立刻服務 detail 頁
- 後續清理可在另一 PR
