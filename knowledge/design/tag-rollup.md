# 設計：Tag-based 群組成本 rollup（階段 15）

> spec：[`specs/023-tag-group-rollup/`](../../specs/023-tag-group-rollup/)

## 一句話

在既有 `aggregate_usage` 加 `group_by="tag"`：JOIN `member_tags` 讓「成員掛 N tag → 用量計入
N 個 tag」的重疊**自然產生**，這正是「tag 總額 = 該 tag 成員各自相加」的定義。無新表、無 migration。

## JOIN 拓撲

```
call_records ──┐
               │ allocation_id
          allocations ──┐
                        │ member_id
                   member_tags
                        │ GROUP BY tag
                        ▼
              一個 tag 一列（token / cost / count 的 SUM）
```

關鍵：`member_tags` 是 `(member_id, tag)` join table。成員掛 2 個 tag → 2 列 → 其每筆
call 與 2 個 tag 各配一次 → 計入 2 個 tag。**這是刻意的重疊，不是 bug。**

## 重疊語意自證

「`class-101` 的 total = class-101 所有成員的個別 total 之和」（SC-002）為何成立：
GROUP BY tag 後，每筆 call 落在「它的成員所屬的 tag」群組被加總一次；成員掛多 tag → 該 call
在多個 tag 群組各加一次。所以一個 tag 群組內加總的 = 該 tag 所有成員的 call = 成員各自相加。

推論：**各 tag 加總 ≠ 平台總額**（重疊成員被多算）。故 UI 常駐標示此性質，且平台總額仍以
member/allocation/model 維度為準（FR-007）。

## 設計決策（research 摘要）

| 決策 | 選擇 | 為何 |
|------|------|------|
| 聚合來源 | 既有 `member_tags` distinct | 不新增 entity/表（呼應「Tag 設計：先用 distinct 推導」lesson） |
| tag 時間版本化 | **不做** | 採查詢當下歸屬；班級歸屬穩定、版本化複雜度不符需求（YAGNI） |
| 重疊 | **不去重** | 刻意語意——admin 要的就是「這個班總共用多少」；UI 標示即可 |
| 下鑽 | 重用 member 分支 + tag 過濾 | 不重寫 member 聚合邏輯（避免「兩份必 drift」） |
| API | 擴充 `group_by=tag` + 新增 `/usage/tag/{tag}/members` | 聚合同形塞既有端點（自動獲 CSV/JSON）；下鑽異形用獨立端點 |
| 權限 | admin-only，不進 `/me` | tag 是治理視角；成員看跨成員聚合 = 洩漏（FR-012/013） |

## 觸發來源 / 端點

| 端點 | 行為 |
|------|------|
| `GET /admin/usage?group_by=tag` | 各 tag 聚合（含 `/usage.json`、`/usage.csv`） |
| `GET /admin/usage/tag/{tag}/members` | 某 tag 的成員明細下鑽 |

## 已知限制

- **各 tag 加總會超過平台總額**（重疊成員被多算）——by design，UI 標示。
- **tag 採查詢當下歸屬**——不反映「呼叫當時的 tag」。學期中轉班會讓歷史用量「跟著新 tag 走」。
  若未來需精確歷史歸屬再評估 tag 版本化。
