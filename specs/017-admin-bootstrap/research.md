# Phase 0 Research: 管理員 Bootstrap 與部署強化

## R1: 首位 admin 佈建機制 — CLI + Helm hook Job

**Decision**: 新增 `ai_api.cli.create_admin`，以 Helm `pre-install,pre-upgrade` hook Job（`hook-weight: "1"`）執行，排在既有 migrate Job（`weight "0"`）之後、app Deployment 滾動更新之前。

**Rationale**:
- 既有 `migration-job.yaml` 已建立「一次性 Job、同 image、`envFrom` 同一 Secret、helm hook」模式；佈建 Job 是其自然兄弟，維運心智模型一致。
- Helm 依 hook-weight 升序執行並等待每個 hook 完成，故 weight 1 保證 schema 就緒後才佈建（滿足 FR-004 排序）。
- idempotent 設計使每次 `helm upgrade` 重跑安全（`hook-delete-policy: before-hook-creation,hook-succeeded` 比照 migrate）。

**Alternatives considered**:
- 啟動時依環境變數自動建立：被否決。N 個 replica 啟動會競爭、需加鎖；把一次性動作耦合到每個 pod 生命週期，難以重跑／變更。
- 維持 token + curl 手動流程：被否決。需把 bootstrap token 交給操作者、易錯、無法自動化、無 idempotent 保證。

## R2: OIDC 預建 vs 本地密碼

**Decision**: CLI 支援 `--provider {google_oidc,local_password}`，預設 `google_oidc`。
- `google_oidc`：以 `MemberService.create(provider=google_oidc, send_invitation=False)` 建立無密碼成員，再 `set_is_admin(True)`。該人首次 Google 登入時，`_find_or_create_oidc_member` 依 email 比對到既有成員並回傳（既有行為，`auth.py:233`），即取得 admin session。**全程無需傳遞 token 或密碼**。
- `local_password`：以 `create(provider=local_password, send_invitation=True)`，產生一次性邀請連結（`invitations.issue`，既有流程），CLI 印出供首次設定密碼。

**Rationale**: 多數正式部署採 Google OIDC（chart 已接 `googleOauth.*`）。OIDC 預建零密碼傳遞，安全且零手動步驟（SC-001）。

**Alternatives considered**: 只支援 local_password — 被否決，OIDC 組織會被迫走密碼路徑、多一份機密管理。

## R3: idempotent 與衝突語意

**Decision**:
- 指定 email 尚不存在 → 建立 + 升級為 admin。
- 指定 email 已存在且 provider 相符 → 確保 `is_admin=True`（`set_is_admin` 對已是 admin 者為 no-op），回報「已存在，未變更／已升級」，退出碼 0。
- 指定 email 已存在但 provider 不符 → 拒絕並退出非 0，明確訊息（不覆寫既有身分，FR-005、對齊 `auth.py:234` 的 provider_conflict 精神）。
- 「已有其他 admin、但指定 email 不存在」→ 仍建立並升級指定 email（不跳過，Edge Case）。

**Rationale**: 滿足 FR-003 idempotent 與 FR-005 衝突保護；重用既有 `set_is_admin` 連帶獲得「不可降級最後一位 admin」保護（本功能只升級，不觸發降級，FR-011 不受影響）。

## R4: 啟動防呆判定訊號

**Decision**: 在 `create_app()` 既有 fail-fast 區塊（緊接 `get_fernet()` 之後）加入：

```python
if settings.cookie_secure and settings.admin_bootstrap_token in ("", DEFAULT_ADMIN_BOOTSTRAP_TOKEN):
    raise RuntimeError("ADMIN_BOOTSTRAP_TOKEN 仍為空或預設值，拒絕在 production（COOKIE_SECURE=true）啟動")
```

把預設值字面值抽成 `config.DEFAULT_ADMIN_BOOTSTRAP_TOKEN` 常數，供防呆與測試共用。

**Rationale**:
- 重用 `COOKIE_SECURE`：任何 HTTPS 正式部署本就會開啟它，無需新增 `APP_ENV`（YAGNI、FR-008）。
- 比照既有 Fernet key fail-fast（`test_startup_crypto.py`）：production 誤帶後門 → pod CrashLoopBackOff，逼修正（FR-006、SC-003）。
- dev（`COOKIE_SECURE=false`）維持預設可用（FR-007）。

**Alternatives considered**: 新增 `APP_ENV=production` — 被否決（多一個易漏設的旋鈕）。只 WARNING 不擋 — 被否決（保護力不足，無法達成 SC-003 的 100%）。

## R5: 錯誤訊息不洩漏密鑰（可觀測性）

**Decision**: 啟動防呆與 CLI 訊息只描述「為空／為預設值」，**絕不印出** token 實際值；CLI 對 local_password 印出的是一次性邀請連結（既有設計即一次性），OIDC 路徑不印任何密鑰。

**Rationale**: 對齊 Principle IV（日誌與訊息不洩漏密鑰／PII）。

## R6: 測試策略（TDD）

| 測試 | 類型 | 對應 |
|------|------|------|
| 乾淨 DB 以 OIDC 佈建 → 成員存在、is_admin、google_oidc、無密碼 | integration | FR-001/002, US1-AS1 |
| 重跑佈建 → 不重複、退出 0 | integration | FR-003, US1-AS3, SC-002 |
| email 已存在但 provider 不符 → 非 0 退出、明確訊息 | integration | FR-005, Edge |
| local_password 佈建 → 產生邀請、印出連結 | integration | FR-002, US1-AS4 |
| 已有他 admin、指定 email 不存在 → 仍建立升級 | integration | Edge |
| cookie_secure=true + 預設 token → create_app() raise | integration | FR-006, US2-AS1 |
| cookie_secure=true + 空 token → raise | integration | FR-006, US2-AS2 |
| cookie_secure=true + 自訂 token → ok | integration | US2-AS3 |
| cookie_secure=false + 預設 token → ok | integration | FR-007, US2-AS4 |
| Helm 渲染含 bootstrap-admin Job、hook 排序在 migrate 後、envFrom secret、可停用 | integration（helm template） | FR-009 |

無 NEEDS CLARIFICATION 待解。
