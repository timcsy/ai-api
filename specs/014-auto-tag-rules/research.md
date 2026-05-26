# Phase 0 — Research

## R1：ReDoS 護欄策略（不上 re2）

**Decision**：標準 `re` + 三道護欄：
1. **強制 anchor**：儲存時若 pattern 無 `^`/`$` 自動包成 `^(?:<pattern>)$`（local-part 完整比對語意）
2. **輸入長度上限**：比對前 `local_part[:64]`；超過直接視為不匹配
3. **複雜度檢查**：compile 後掃 pattern 字串，拒絕已知 ReDoS 反模式——巢狀量詞 `(...+)+` / `(...*)*` / `(...+)*`、以及過多 `*`/`+`（> 10 個量詞）

**Rationale**：
- 規則只在 **cold path（建立成員）跑一次**，不在登入 hot path → 即使單條稍慢也不影響線上
- re2 要加 native 編譯依賴 + Docker build 複雜度，對「< 20 條規則、單次評估」過頭
- anchor + 64 長度上限已大幅壓縮回溯空間；複雜度檢查擋掉教科書級 ReDoS

**Alternatives considered**：
- **re2**：線性時間保證，但新依賴 + 編譯；YAGNI for cold-path single eval
- **signal-based timeout**：`signal.alarm` 不能在非主執行緒用（async worker），不可靠
- **完全禁 regex 只給 glob**：使用者明確需要學號格式（`[a-z]{0,2}\d{6,}`），glob 表達不出「剛好 N 位數字」

## R2：註冊 hook 位置

**Decision**：在既有兩個「新建 member」點，建立成功（flush）後呼叫
`TagRuleService.apply_to_new_member(session, member)`：

1. `src/ai_api/api/auth.py` 的 `_find_or_create_oidc_member` —— 只在走 `new = Member(...)` 分支（首次 OIDC 註冊）後呼叫，已存在 member 不呼叫
2. `src/ai_api/services/members.py` 的 `MemberService.create` —— admin 手動建立成員後呼叫

**Rationale**：
- 這兩處是「新成員誕生」的唯二入口（local login 不建立 member；allocation 的 `_ensure_external_member` 是 Phase 1 back-compat 的外部 subject，不算組織成員 → 不掛）
- 不做 middleware / 不做事件匯流排——YAGNI，兩個直接呼叫最清楚
- 「首次」語意天然成立：兩處都只在「member 不存在 → 建立」時跑

**Edge**：local password 成員由 admin 建立 → 也應自動分類（admin 建學生帳號照樣貼 student）→ 所以 `MemberService.create` 也要掛。

## R3：Matcher 設計與 fallback

**Decision**：`matcher_type` enum 4 值：
- `email_localpart_regex`：`re.fullmatch(anchored_pattern, local_part[:64])`
- `email_suffix`：`email.lower().endswith(pattern.lower())`
- `email_domain`：`email.split("@")[-1].lower() == pattern.lower()`
- `always`：catch-all（永遠命中），作為 fallback

**Rationale**：
- `always` 當 fallback 比「特殊 fallback 欄位」乾淨——它就是一條排最後的規則
- suffix 和 domain 看似重疊，但 suffix 可比對 `@students.school.edu` 這種子網域結尾、domain 是完全比對 → 兩者都留有實際用途
- 全部 case-insensitive（email 慣例）

## R4：評估演算法

**Decision**：

```
def evaluate(email) -> matched_rule | None:
    for rule in sorted(enabled_rules, key=order_index):
        if matches(rule, email):
            return rule        # first-match-wins
    return None                # 無命中（且無 always 規則）
```

貼 tag：`MemberTagService.add(member_id, [rule.tag], source="auto", rule_id=rule.id)`。
只貼**一個** tag（first-match 命中的那條）。若要一個 member 同時 student + 某單位 tag，admin 要嘛靠手動、要嘛這個版本不支援多重 auto tag（spec 為 first-match-wins 單一）。

**Rationale**：spec FR-009 明確 first-match-wins 單一；多重 auto tag 留後續（YAGNI）。

## R5：MemberTag.source 的相容性

**Decision**：
- `source` 欄：`manual` | `auto`，預設 `manual`（既有資料 backfill `manual`）
- `rule_id` 欄：nullable，auto 時記命中的 rule id
- 既有 `MemberTagService.add` 加參數 `source="manual"`（預設不變）、`rule_id=None`
- 既有所有讀 tag 的地方（access policy / 診斷 / tag 詳情 / visible-models）**不看 source** → 行為零變化（SC-005）

**Rationale**：source 純 metadata；access 決策只看 tag 字串集合，與來源無關。

## R6：規則排序的儲存

**Decision**：`order_index` 整數欄；reorder endpoint 接受「完整 id 順序陣列」一次重寫所有 order_index（避免逐筆 swap 的中間態）。

**Rationale**：規則 < 20 條，一次全寫簡單可靠；不需 fractional indexing。

## R7：「測試 email」endpoint

**Decision**：`POST /admin/tag-rules/test` body `{email}` → 回 `{matched_rule_id, matched_tag, matcher_type}` 或 `{matched: false}`。純評估，不寫 DB、不建 member。

**Rationale**：滿足 FR-015 / SC-001；admin 設規則時即時驗證，降低「設錯規則貼錯一批人」風險。

## R8：前端頁面位置

**Decision**：規則管理 UI 不加新 sub-nav 條目（維持 Phase 5.1 的 6 條）；放在 **Tag 頁的一個區塊 / tab**：`/admin/tag` 增「自動標籤規則」分頁，或 Tag 列表頁上方加「規則」按鈕進 `/admin/tag/rules`。

**Rationale**：呼應 Phase 5.1「不要再增加 nav 雜亂」的教訓；規則本質是 tag 的衍生管理，歸在 Tag 區合理。
