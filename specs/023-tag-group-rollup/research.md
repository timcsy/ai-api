# Phase 0：研究與技術抉擇

格式：**Decision / Rationale / Alternatives**。

---

## R1：tag 聚合的 JOIN 拓撲與重疊語意

**Decision**：`CallRecord JOIN Allocation ON allocation_id JOIN MemberTag ON
Allocation.member_id = MemberTag.member_id`，`GROUP BY MemberTag.tag`。

**Rationale**：
- `member_tags` 是 `(member_id, tag)` 的 join table。一位成員掛 N 個 tag → N 列。
  把它 JOIN 進來後，該成員的每一筆 `CallRecord` 會與其 N 個 tag 各配一次 →
  **自然產生「用量計入每個 tag」的重疊**，正是 spec FR-005 要的語意，零額外邏輯。
- 不需要 Member 表（tag 聚合不需 member display name；下鑽才需要）——少一個 JOIN。
- 與既有三個分支同構（都 JOIN Allocation），沿用既有 `base_filters`（success / 時間區間 /
  member-scope）。

**重疊的正確性自證**：tag 聚合的某 tag 數字 = 該 tag 所有成員的個別數字之和（SC-002）。
因為 GROUP BY tag 後，每筆 call 在「它的成員所屬的那個 tag」群組內被加總一次；成員掛多 tag
時該 call 在多個 tag 群組各加一次——這正是「成員各自相加」的定義（成員 C 同時算進 class-101
與資訊社）。

**Alternatives considered**：
- **先查 distinct tag、再對每 tag 跑一次 member 聚合**：N+1 查詢、慢；JOIN 一次解決
- **去重（一成員只算進「主 tag」）**：違反 spec——成員無「主 tag」概念，且 admin 要的就是
  「這個班的人總共用多少」，去重反而錯

---

## R2：tag 不做時間版本化

**Decision**：聚合採「**查詢當下**成員的 tag 歸屬」，不追溯「呼叫發生當時該成員掛哪些 tag」。

**Rationale**：
- `member_tags` 無歷史版本（只有 `added_at`，無 `removed_at` / 版本鏈）。要做「呼叫當時的 tag」
  得為 tag 歸屬建時間版本化表 + 每筆 call 快照 tag——複雜度爆炸。
- 業務上 tag = 班級／社團，相對穩定；學期中轉班罕見。YAGNI。
- spec 假設已明文記錄此限制。

**Alternatives considered**：
- **每筆 CallRecord 快照當時 tag**：schema 變更 + 每 call 寫多列；過度
- **tag 歸屬版本化表**：同上，無當前需求

---

## R3：下鑽（某 tag 的成員明細）實作

**Decision**：重用既有 member 維度聚合 + 「該成員 ∈ 此 tag」過濾。新增
`aggregate_usage_for_tag_members(tag, ...)` 或在 `aggregate_usage` 加可選 `tag_filter` 參數，
回該 tag 底下每位成員的 `UsageItem`（沿用既有 member 分支的 row 形狀）。

**Rationale**：
- 下鑽就是「member 維度，但只看這個 tag 的成員」——member 分支已有完整邏輯（display_name、
  token 拆分、cost），加 `WHERE member_id IN (SELECT member_id FROM member_tags WHERE tag=:tag)`
  即可，不重寫。
- 回傳形狀與既有 member 維度一致 → 前端可重用既有列渲染。

**Alternatives considered**：
- **另寫一套 tag-member 聚合**：重複 member 分支邏輯，違反「同一概念兩份必 drift」lesson
- **前端自己 filter**：前端拿不到完整成員用量、且會洩漏跨成員資料給前端

---

## R4：API 形狀——擴充 enum vs 新端點

**Decision**：
- **tag 聚合**：擴充既有 `GET /admin/usage?group_by=tag`（與 `/usage.json`、`/usage.csv` 一致）——
  enum 加一個值，回傳形狀不變（`UsageItem` list）
- **tag 成員下鑽**：新增 `GET /admin/usage/tag/{tag}/members?from=&to=`，回該 tag 成員的 `UsageItem` list

**Rationale**：
- tag 聚合與既有三維度同形（一個 group_key + 數字），塞進既有端點最一致、自動獲得 CSV/JSON 匯出
- 下鑽是不同形狀的查詢（指定 tag、回成員），用獨立端點清楚；URL 含 tag path 參數
- 非破壞：既有 enum 值與端點不動

**Alternatives considered**：
- **下鑽也塞 group_by**：`group_by=member&tag=X`——語意混淆（group_by=member 卻又限定 tag）；
  獨立端點更清楚
- **GraphQL / 自訂 query DSL**：過度

---

## R5：service_only / member-scope 與 tag 維度的互動

**Decision**：tag 維度**支援既有 `service_only` filter**（沿用 base_filters）；但**不接受
`member_id` scope**（tag 是 admin 跨成員視角，member-scope 對它無意義）。

**Rationale**：
- `service_only`（只看服務型分配）對 tag 聚合仍有意義（admin 想看某班的 service 流量），自然支援
- `member_id` scope 是 Phase 018 給 `/me` 用的「只看自己」；tag 聚合本就 admin-only、跨成員，
  member-scope 不適用——明確不接受，避免誤用

**Alternatives considered**：
- **tag + member_id 同時**：無意義組合（一個成員 vs 一群成員），拒絕

---

## R6：權限——admin-only，不進 /me

**Decision**：tag 聚合與下鑽端點掛在既有 admin usage router（已 `require_admin`）；**不**在 `/me`
路徑提供任何 tag 聚合。

**Rationale**：
- spec FR-012/013：tag 是治理／組織端視角；成員看到跨成員聚合 = 洩漏別人用量
- 既有 `/admin/usage` router 已有 admin 保護，新增值/端點自動受益

**Alternatives considered**：
- **讓成員看自己所屬 tag 的聚合**：那會讓成員看到同 tag 其他人的用量；拒絕

---

## R7：前端 UI——Tag 視圖 + 下鑽 + 重疊提示

**Decision**：
- `/admin/usage` 的 group-by `Select` 加「依 Tag」選項（沿用既有 Select pattern）
- 選 Tag 時，列表每列一個 tag + 數字；列可點開 → 展開該 tag 成員明細（呼叫下鑽端點）
- Tag 視圖固定顯示一句重疊提示：「成員可掛多個 tag，各 tag 加總可能重複計算、不等於平台總額」

**Rationale**：
- 沿用既有 usage.tsx 的 group-by 切換 + 列表渲染，最小改動
- 重疊提示常駐（非 tooltip）——這是會影響判讀的重要前提，不能藏

**Alternatives considered**：
- **獨立 tag 頁面**：與既有 usage 頁分裂，違反「同一概念集中」；放同頁切換更一致
- **重疊提示只放 tooltip**：太容易被忽略，改判讀錯誤；常駐文字較安全

---

## 研究結論

所有技術未知收斂，無 NEEDS CLARIFICATION。可進入 Phase 1。
