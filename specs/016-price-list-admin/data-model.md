# Phase 1 — Data Model

## 1. PriceList（既有，**無變更**）

沿用既有表，不加欄位、不改約束。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | str(26) ULID PK | |
| `provider` | str(64) | 供應商（對應 catalog model 的 provider）|
| `model` | str(128) | **去 provider 前綴**的 model 識別字（計費查價的 key）|
| `input_per_1k_tokens_usd` | Numeric(12,8) | 輸入單價（USD / 1K tokens）|
| `output_per_1k_tokens_usd` | Numeric(12,8) | 輸出單價 |
| `effective_from` | datetime(tz) | 生效時間（point-in-time 錨點）|
| `created_at` | datetime(tz) | |
| `created_by` | str(128) | `cli:<user>` 或 `admin`（UI 新增）|
| `source_note` | text NULL | 來源備註 |

**唯一性**：`UniqueConstraint(provider, model, effective_from)`（既有）→ 重複版本由 DB 擋。
**索引**：`(provider, model, effective_from)`（既有）→ 選版查詢主路徑。

**本 feature 不需 migration。** audit 加 1 個 enum 值（見下），`Enum(native_enum=False, length=64)` 存 VARCHAR，無 schema 變更。

## 2. AuditEventType（既有 enum，加 1 值，無 migration）

| 新值 | 觸發 |
|---|---|
| `price_version_added` | admin 由 UI 新增價格版本（details: provider, model, effective_from）|

CLI 匯入維持現況（不寫此 audit；CLI 是離線批次工具）。

## 3. 查詢 / DTO 形狀（非持久化）

```python
# GET /admin/prices —— 以 catalog 為主清單
class CatalogPriceRow(TypedDict):
    provider: str
    model: str            # 去前綴 key（計費用）
    slug: str             # catalog slug（顯示用）
    display_name: str
    priced: bool
    current: CurrentPrice | None   # 目前生效；無則 None（未定價）

class CurrentPrice(TypedDict):
    input_per_1k: str     # Decimal 序列化為字串避免精度流失
    output_per_1k: str
    effective_from: str   # ISO

# GET /admin/prices/history?provider=&model= —— 該 key 全版本
class PriceVersion(TypedDict):
    id: str
    input_per_1k: str
    output_per_1k: str
    effective_from: str
    source_note: str | None
    created_at: str
    created_by: str
    is_current: bool
```

**選版規則**（`current` 與 `is_current`）：`effective_from <= now` 中最新的一筆 = current；未來生效版本 `is_current=false`（在 history 可標「排程生效」）。等同 `pricing.lookup_price_for_call(call_time=now)` 的語意。

## 4. pricing.py 新增方法（複用既有，不改既有簽名）

- `list_catalog_prices(session, now) -> list[CatalogPriceRow]`：join catalog × 各 key 的 current price
- `list_history(session, provider, model) -> list[PriceVersion]`
- `create_version(session, ...) -> PriceList`：驗證非負 + tz-aware；唯一衝突 raise（API 轉 409）

既有 `lookup_price_for_call` / `calculate_cost` **不動**。
