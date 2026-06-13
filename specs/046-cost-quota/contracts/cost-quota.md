# Contract: 成本制配額

四個契約面。錯誤封包沿用既有 `{error:{code,message,request_id}}`。

## 1. Admin 分配 create / update — 收選填花費上限

**端點**：既有 `POST /admin/allocations`、`PATCH /admin/allocations/{id}`（或既有配額編輯端點）
**新增欄位（請求）**：

```jsonc
{ "quota_cost_usd_per_month": 5.00 }   // 選填；null/省略 = 不設上限；< 0 → 422
```

- 接受 `null`（清除上限）、正數（設上限，含 0）、省略（不變）。
- 變更留稽核（沿用既有 allocation 更新的 audit，記新值）。
- **回應**：分配序列化多 `quota_cost_usd_per_month`。

## 2. Proxy 同步端點 — 花費超額拒絕

**端點**：所有計費端點（chat/responses + registry：embedding/ocr/image/rerank/audio/moderation/search/image_edit）共用 preflight。

```
preflight: 若 allocation.quota_cost_usd_per_month 非 null 且 current_month_cost ≥ cap
  → 403 { "error": { "code": "cost_quota_exceeded",
                     "message": "已達本月花費上限（$X / $Y）" } }
  → 記一筆 CallRecord(outcome=rejected_cost_quota_exceeded, status=403, allocation 綁定)
```

- token 上限與花費上限**並列**：任一達到即擋（取較嚴者）。
- 未設花費上限（null）→ 此檢查跳過，行為與現況一致。
- 未定價呼叫（`cost_usd` NULL）不增加累計 → 不會因花費上限被擋。

## 3. 用量顯示 — 本月花費 / 上限

**端點**：`/me/usage`、`/me/allocations`、admin 用量每分配。
**新增欄位（回應，每分配）**：

```jsonc
{
  "cost_used_this_month": "4.90",          // Decimal 字串
  "quota_cost_usd_per_month": "5.000000"   // 或 null
}
```

## 4. Realtime 連線中花費把關

**端點**：`/v1/realtime`（階段 32）
**行為**：

```
連線建立：preflight 含 cost 檢查（同 §2，超額即 close 不開串流）
連線中：旁路 watcher 每 N 秒：
  committed = current_month_cost(allocation)        // 已落帳（不含本連線）
  running   = session_running_cost(sess, price)     // 本連線進行中累計
  若 committed + running ≥ cap → close(policy violation 1008, reason="本月花費上限")
                                  + 已累計時長落帳（沿用「任何 close 路徑都落帳」）
```

- 容差：最多「上限 + 一個 re-check 週期」的小幅超出（與既有撤回延遲同語意）。

## 契約測試（合併前必過）

1. 分配設花費上限 $X，混合 chat（token）+ OCR/realtime（非 token）累計花費達 $X → 後續呼叫 403 `cost_quota_exceeded`，且落一筆 `rejected_cost_quota_exceeded`。
2. 分配**未**設花費上限 → 大量非 token 呼叫不被擋（token 配額行為零回歸）。
3. 分配同設 token+cost 上限 → 先達到者擋（兩種各驗一次）。
4. 未定價模型呼叫 → 不增加累計、不被花費上限擋。
5. realtime 連線中累計花費超額 → N 秒內 close（mock provider WS）+ 已累計時長落帳。
6. 自適應配額池跑一輪 → 各分配 `quota_cost_usd_per_month` 不變（只 token 額度被再分配）。
7. `current_month_cost` = 該分配本月成功呼叫 `cost_usd` 之 `Decimal` 總和（含非 token，未定價以 0 計）。
