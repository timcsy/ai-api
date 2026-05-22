# Phase 0 Research: 階段 4 — Model Catalog

---

## 1. list-valued field 儲存方式

**決策**：用 SQLAlchemy `JSON` column 儲存 list（capabilities、modality_input、
modality_output、recommended_for、tags）。Postgres 對應 JSONB，SQLite 對應 JSON。
filter 時整批 SELECT 後 Python 端用 set 交集處理。

**理由**：
- 首版 ≤ 100 active models，純 Python filter 開銷可忽略
- 跨方言 portable（不依賴 Postgres JSONB containment operator）
- 演算法簡單：`required_caps.issubset(model.capabilities)` 一行

**已評估**：
- 多對多關聯表（model_capability、model_modality 各一表）：DB schema 複雜，
  查詢要 JOIN，但對 < 100 row 沒效益
- Postgres JSONB containment + GIN index：未來規模 > 1k 時可改；首版過早
  優化

---

## 2. Filter AND 語意實作

**決策**：純函式 `filter_models(models, criteria)`：

```python
def filter_models(models: list[ModelCatalog], *,
                  capabilities: set[str] | None,
                  modality_input: set[str] | None,
                  cost_tier: str | None,
                  ...) -> list[ModelCatalog]:
    def matches(m):
        if capabilities and not capabilities.issubset(set(m.capabilities)):
            return False
        if modality_input and not modality_input.issubset(set(m.modality_input)):
            return False
        if cost_tier and m.cost_tier != cost_tier:
            return False
        return True
    return [m for m in models if matches(m)]
```

**理由**：
- 一個函式涵蓋所有 filter 規則；boundary case unit-test 容易
- 與 spec FR-007 條文 1:1 對應
- 重複的 query string key（capability=A&capability=B）由 FastAPI Query 自動
  轉成 list；轉 set 後 issubset 即 AND

---

## 3. Filter 大小寫不敏感

**決策**：API 層在轉 set 前 `.lower()` 全部 query 值；YAML 載入時也 lowercase
所有 enum-style 欄位（modality_*、capabilities、cost_tier、status）。

**理由**：避免在 filter 邏輯處做轉換；source-of-truth 統一小寫。

**注意**：`display_name` 與 `description` 維持原大小寫（人類可讀內容）。

---

## 4. YAML schema 驗證

**決策**：用 Pydantic `BaseModel` 建一個 `ModelCatalogYAML` schema，CLI 載入
時對每筆 entry validate；任何錯誤 → 整批 abort（transaction rollback）。

```python
class ModelEntry(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]+/[a-z0-9.-]+$")
    provider: str
    display_name: str
    family: str
    description: str
    modality_input: list[Literal["text","image","audio","video","embedding"]]
    modality_output: list[Literal["text","image","audio","video","embedding"]]
    capabilities: list[Literal["chat","vision","function-calling","json-mode",
                                "tool-use","streaming","reasoning","embedding",
                                "fine-tuning"]]
    context_window: int
    cost_tier: Literal["low","medium","high"]
    recommended_for: list[str] = []  # free-form
    tags: list[str] = []
    example_request: dict
    official_doc_url: str | None = None
    status: Literal["active","preview","deprecated"] = "active"
    deprecation_note: str | None = None
```

**理由**：
- 列舉值用 `Literal` 直接限制 → 明確錯誤訊息
- `recommended_for` 不限制（spec 已明定為 free-form scenario tag）
- slug pattern 強制 `provider/model` 格式

---

## 5. Upsert 與防誤刪

**決策**：CLI 流程：

```python
async def load_models(yaml_path: Path) -> tuple[int, int]:
    """Returns (inserted, updated). Never deletes."""
    entries = parse_and_validate(yaml_path)
    for entry in entries:
        existing = await db.get(ModelCatalog, entry.slug)
        if existing:
            update_fields(existing, entry, preserve=["created_at"])
        else:
            db.add(ModelCatalog(**entry.dict(), created_at=now, updated_at=now))
    await db.commit()
```

**理由**：
- 不掃 DB 找「YAML 沒列的 model」→ 自然 idempotent + 防事故 wipe
- `updated_at` 永遠 refresh；`created_at` 保留

**已評估**：
- 用 `INSERT ... ON CONFLICT` Postgres native upsert：寫法簡潔，但 SQLite 語
  法不同；Python 端 `get → update or insert` 跨方言一致
- 「diff 列出將刪除的 model 並二次確認」：違反 spec FR-005「不刪除」承諾

---

## 6. Facet 計算

**決策**：facet API 在 Python 端對 active models 跑：

```python
def compute_facets(models: list[ModelCatalog]) -> dict[str, dict[str, int]]:
    dims = {
        "modality_input": defaultdict(int),
        "modality_output": defaultdict(int),
        "capabilities": defaultdict(int),
        "cost_tier": defaultdict(int),
        "recommended_for": defaultdict(int),
        "family": defaultdict(int),
        "tags": defaultdict(int),
    }
    for m in models:
        for v in m.modality_input: dims["modality_input"][v] += 1
        # ... 同理
        dims["cost_tier"][m.cost_tier] += 1
        dims["family"][m.family] += 1
    # 保證 schema 穩定：即使某 dim 全 0 也回空 dict
    return {k: dict(v) for k, v in dims.items()}
```

**理由**：純函式、O(N × dims)、< 100 models 完全可忽略開銷；schema 穩定
（dimension key 不依資料動態決定）。

---

## 7. 權限：require_active_member 依賴

**決策**：在 `api/deps.py` 新增 `require_active_member(session=...)` 依賴：

```python
async def require_active_member(
    session_obj: Session = Depends(get_session_from_cookie),
) -> Member:
    member = session_obj.member
    if member.status != MemberStatus.active:
        raise HTTPException(403, detail=_err("member_disabled", ...))
    return member
```

**理由**：
- 既有 `get_session_from_cookie` 已 cover 401（無 session 即拒）
- catalog 不需 admin 權限，但要求 active member 即可分流「可看 / 不可看」
- 未來其他「member-only」endpoint 也可重用

---

## 8. URL slug 編碼

**決策**：slug 含 `/`（如 `azure/gpt-4o-mini`），路徑參數用 URL-encode
（`azure%2Fgpt-4o-mini`），FastAPI 自動 decode。

**已評估**：
- 改用 query param `?slug=...`：違背 REST 慣例
- 拆成 `/catalog/models/{provider}/{name}`：路徑層級變動較大、middleware 處
  理麻煩

---

## 9. PriceList 對齊 SOP

**決策**：spec FR-022 NON-GOAL「即時定價」延後；docs/model-catalog.md 記載
SOP：

1. 新增 model 時，PriceList YAML 與 model_catalog YAML 同 PR 提交
2. slug 命名規則 `azure/gpt-4o-mini` ↔ PriceList `provider=azure, model=gpt-4o-mini`
3. 未來整合時：在 catalog detail endpoint 加 `pricing` 欄位，from PriceList join

---

## 10. NEEDS CLARIFICATION

無未決。
