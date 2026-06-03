# Phase 1：Quickstart — tag 群組 rollup

以整合測試情境定義驗收。每條對應 Phase 2 一條測試。

## 前置

- 既有 admin 可登入；既有 `member_tags`、`call_records` 表
- 測試走既有 in-memory SQLite contract pattern + Docker-free 整合測試

## 情境 1：tag 聚合 = 成員各自相加（US1，SC-002）

**步驟**：
1. seed 成員 A（tag `class-101`）、B（tag `class-101`）
2. A 在區間內成功呼叫累計 1000 tokens、B 累計 500
3. `GET /admin/usage?group_by=tag&from=&to=`

**預期**：
- 回應 `items` 含一列 `group_key=class-101`，`total_tokens=1500`（= A + B）
- `call_count` = A、B 呼叫次數之和

**驗收**：tag 數字逐筆等於成員各自相加。

## 情境 2：多 tag 成員重疊正確計入（US2，FR-005）

**步驟**：
1. 成員 C 同時掛 `class-101` 與 `資訊社`，呼叫累計 300 tokens
2. 分別查兩個 tag

**預期**：
- `class-101` 含 C 的 300（加上情境 1 的 A+B）
- `資訊社` 也含 C 的 300
- C 的用量在兩個 tag 都被計入（刻意重疊）

**驗收**：跨 tag 重疊成員的用量在每個所屬 tag 都正確出現。

## 情境 3：時間區間正確過濾（US1）

**步驟**：
1. 成員 A 在區間內呼叫 1000、區間外呼叫 9999
2. 查 tag 用量

**預期**：`class-101` 只計入區間內的 1000，區間外 9999 不計。

## 情境 4：tag 成員下鑽（US2）

**步驟**：
1. `GET /admin/usage/tag/class-101/members?from=&to=`

**預期**：
- 回 `members` list，含 A、B（與 C 若 C 也在 class-101）各自的 `UsageItem`
- 每位成員的 token / cost / count 與其個別用量一致
- 形狀與既有 `group_by=member` 維度的 item 一致

## 情境 5：service_only filter 對 tag 維度有效（R5）

**步驟**：
1. 成員 D（tag `bots`）有一筆 service allocation 呼叫 + 一筆非 service 呼叫
2. `GET /admin/usage?group_by=tag&service_only=true`

**預期**：`bots` 只計入 service allocation 的用量。

## 情境 6：tag 維度匯出 CSV / JSON（US3，FR-011）

**步驟**：
1. `GET /admin/usage.csv?group_by=tag&from=&to=`
2. `GET /admin/usage.json?group_by=tag&from=&to=`

**預期**：
- CSV 每列一個 tag，欄位含 token/cost/count，數字與 `/usage` 一致
- JSON 為 `UsageItem` array，結構與既有維度一致

## 情境 7：member 隔離——成員無法取得跨成員 tag 聚合（FR-013，SC-005）

**步驟**：
1. 以一般成員 session（非 admin）呼叫 `GET /admin/usage?group_by=tag`
2. 嘗試 `GET /admin/usage/tag/class-101/members`

**預期**：兩者皆 401/403（admin-only）；`/me` 路徑無任何 tag 聚合端點。

## 情境 8：既有維度零退化（SC-004）

**步驟**：跑既有 `group_by=member/allocation/model` 的用量測試。

**預期**：全數通過、數字與行為不變。

---

## 整合測試命名建議

| 情境 | 測試檔 | 函式 |
|------|--------|------|
| 1 | `tests/integration/test_usage_tag_agg.py` | `test_tag_aggregation_equals_member_sum` |
| 2 | 同上 | `test_multi_tag_member_counts_in_each` |
| 3 | 同上 | `test_tag_respects_time_range` |
| 4 | `tests/contract/test_usage_tag.py` | `test_tag_members_drilldown` |
| 5 | 同上（integration） | `test_tag_service_only_filter` |
| 6 | `tests/contract/test_usage_tag.py` | `test_tag_csv_json_export` |
| 7 | `tests/contract/test_usage_tag.py` | `test_tag_endpoints_admin_only` |
| 8 | 既有 `tests/.../test_usage*` | （沿用，確認零退化） |

## 前端煙霧測試（部署後）

1. `/admin/usage` 切「依 Tag」→ 看到各 tag 聚合
2. 點一個 tag → 展開成員明細
3. 確認重疊提示文字常駐
4. 匯出 CSV → 數字與頁面一致
