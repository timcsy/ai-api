# Phase 1 — Data Model

## 無 schema 變更

本 feature **不引入任何新 entity**、不改既有 column、不寫新 migration。所有資料模型沿用 Phase 5（spec line 121「Key Entities: 無新增 entity」）。

## 唯一的衍生「資料」：visibility evaluation 結果

純函式輸出，不入 DB。形狀如下：

```python
class VisibilityCheck(TypedDict):
    check: Literal[
        "credential_gate",      # provider 有 active credential 嗎
        "default_access",       # open / restricted 標記
        "deny_tags",            # member tag ∩ denied_tags 是否為空
        "allow_tags",           # member tag ∩ allowed_tags 是否非空（僅當 restricted）
    ]
    pass_: bool  # True 表示這層通過
    detail: str  # 人類可讀說明


class VisibilityResult(TypedDict):
    visible: bool
    reason_chain: list[VisibilityCheck]
```

**評估順序**（短路）：

1. `credential_gate`：fail → visible=False，rest 不評
2. `default_access`：只是分流，不算 pass/fail
3. `deny_tags`：fail → visible=False
4. `allow_tags`（僅 restricted 時跑）：fail → visible=False
5. 全部通過 → visible=True

## 既有 entity 之關聯使用

新功能會 JOIN 既有 5 個表（無新表）：

- `members`（讀 status）
- `member_tags`（讀 tag 集合）
- `model_catalog`（讀 default_access / allowed_tags / denied_tags / provider）
- `provider_credentials`（讀 status by provider）
- `allocations`（在 member detail 頁讀該 member 的 allocations）

## Migration

**0 個**新 migration。最後一個仍是 `0010_phase5_audit_events`（已合入 main）。
