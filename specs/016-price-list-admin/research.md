# Phase 0 — Research

## R1：「目前生效」選版邏輯 — 複用 point-in-time 語意

**Decision**：列表的「目前生效」價格 = `PriceList` 中該 (provider, model)、`effective_from <= now` 的最新一筆——與 `pricing.lookup_price_for_call(call_time=now)` 同一邏輯。

**Rationale**：UI 顯示的「現在的價格」必須與計費實際用的價格一致，否則 admin 看到的與帳上算的會 drift。直接重用同一查詢語意（甚至同一函式，傳 `call_time=now`）。

**Alternatives**：用 `effective_from` 最大（含未來）（否決：未來排程價不是「目前」生效；計費也不會用）。

## R2：price key 對應 catalog

**Decision**：價目 key = `provider`（catalog model 的 provider 欄）+ `model = catalog slug 去掉 "<provider>/" 前綴`。UI 以 catalog 為主清單，對每個模型用此 key 查價目。

**Rationale**：`proxy/router.py:240` 計費查價用 `provider=<resolved>, model=requested_model.split("/",1)[-1]`。要讓「補了價就算得出成本」，UI 新增與查詢都必須用**同一個 key**。由 catalog 帶出可避免 admin 手拼 `gpt-5.4-mini` vs `azure/gpt-5.4-mini` 之類錯誤。

**Edge**：catalog 已移除、但價目表仍有的舊 model → 歷史檢視仍可查（不以 catalog 為唯一來源；history 端點直接查 price_list）。

## R3：不需 migration / 不改 schema

**Decision**：完全沿用既有 `price_list`（欄位齊全 + `UniqueConstraint(provider, model, effective_from)`）。本 feature 只加：pricing service 方法、admin API、前端頁、1 個 audit enum 值。

**Rationale**：YAGNI。既有表已支援 append-only point-in-time 與唯一性；CLI 已寫此表。新增 UI 不需要任何 schema 改動。audit 值 `price_version_added` 加在 `AuditEventType`（`Enum(native_enum=False, length=64)` → 存 VARCHAR，新增 Python enum 值**不需 migration**，長度足夠）。

## R4：新增的驗證與冪等

**Decision**：`create_version` 驗證：單價非負（`>= 0` 的數值）、`effective_from` tz-aware、tag/欄位齊全；重複 (provider, model, effective_from) → 捕捉 `IntegrityError`（既有唯一約束）回 409 `duplicate_version`。

**Rationale**：與 CLI 的 `IntegrityError` 處理一致；唯一性由 DB 約束保證，API 層轉成明確錯誤碼。呼應 experience「datetime 一律 tz-aware」——`effective_from` 一律帶時區（前端送 ISO，後端比照 CLI `fromisoformat`）。

## R5：admin 端點形態

**Decision**：
- `GET /admin/prices` → 以 catalog 為主，每模型回 `{provider, model_key, slug, display_name, current: {input,output,effective_from} | null, priced: bool}`
- `GET /admin/prices/history?provider=&model=` → 該 key 的所有版本（依 effective_from desc），標 `is_current`
- `POST /admin/prices` → body `{provider, model, input_per_1k, output_per_1k, effective_from, source_note?}` → 201 / 409 duplicate / 422 invalid

**Rationale**：list 服務「未定價可見性」（SC-001），history 服務稽核（US3），create 服務補帳（US2）。history 用 query param（model key 不含 `/`，但 provider+model 兩段用 query 最乾淨）。

## R6：UI 位置

**Decision**：放「觀測」hub 新增「價目」分頁（`/admin/observability/prices`），不增頂層 sub-nav。

**Rationale**：價目屬計費/成本領域，與「用量」同區；比照階段 6 把「分配」加進觀測的做法，守階段 5.1「不增 nav 雜亂」。

## R7：與 CLI 並存

**Decision**：UI 與 CLI 寫同一張 `price_list`、同一唯一約束。兩者皆 append-only。文件標明：批次匯入用 CLI、單筆/臨時補價用 UI。

**Rationale**：FR-012；CLI 仍是大量初始化的好工具，UI 不取代它。
