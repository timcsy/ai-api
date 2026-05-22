# Phase 0 Research: 階段 2 — 身份驗證與成員管理

本檔解決 plan.md 中所有 NEEDS CLARIFICATION 與技術選型。

---

## 1. Google OIDC client library

**決策**：`authlib`（Starlette 整合）

**理由**：
- Pure Python，無 C 依賴；與 FastAPI/Starlette 生態原生相容
- 內建 OIDC discovery、PKCE、ID token 驗證（含 audience、issuer、nonce）
- 維護活躍、文件齊全；支援 mock-friendly 的 OAuth2Client 介面

**已評估**：
- `google-auth` + `google-auth-oauthlib`：Google 官方但對 OIDC 一般化支援
  較弱（更多放在 GCP service account），且依賴鏈較重
- 自行實作：違反 YAGNI 且 PKCE / nonce / discovery cache 都需自管，風險高

---

## 2. 密碼雜湊：Argon2 變體與參數

**決策**：**Argon2id**（透過 `argon2-cffi`），預設參數
`time_cost=3, memory_cost=64MiB, parallelism=4`

**理由**：
- OWASP Password Storage Cheat Sheet 2024 推薦 Argon2id
- `argon2-cffi` 提供自帶版本字串的 hash 輸出，未來調參可直接 `needs_rehash`
  做漸進升級
- 預設參數於現代 CPU 約 50ms：足以阻擋 GPU 爆破，又不顯著拖慢登入

**已評估**：
- bcrypt：可接受但已較老；無 GPU 抗性（記憶體硬性弱）
- scrypt：合格但 Python 生態工具較少
- 純 PBKDF2：合規最低底線，但 GPU 加速可破，不推薦

---

## 3. Session 機制：server-side 表 + cookie 形式

**決策**：
- DB 表 `sessions`（`id` 為隨機 32-byte URL-safe base64 的 SHA-256 指紋）
- cookie 名 `aiapi_session`，值為 token 明文；`HttpOnly`、`Secure`、
  `SameSite=Lax`、`Path=/`
- 每次請求驗證：cookie → SHA-256 → DB lookup → `status=active` and not expired
  → 同時更新 `last_seen_at`

**理由**：
- 滿足 spec FR-015、FR-017、principle 3：可即時撤銷
- cookie 值不存 DB（只存指紋），DB 被讀也無法復原會話 token
- `SameSite=Lax` 對 SSO callback 相容；若未來需跨站，再評估 `None+Secure`

**已評估**：
- Stateless JWT：失去即時撤銷能力（衝突原則 3）；refresh token 又把複雜
  度推回 server 端
- Redis-backed session：scale 更好但引入新依賴；本階段規模不需要
- 純 `signed-cookie` (itsdangerous SecureCookieSession)：撤銷困難；不採用

---

## 4. Rate limit：演算法與儲存

**決策**：**Fixed window per-email**，以 `password_attempts` 表計數

- 查詢「過去 60 秒內同 lower(email) 的 `outcome != success` 計數」
- ≥ 5 → 拒絕新嘗試，回 429；同時寫入 lock 紀錄（`outcome=locked`）
- lock 持續 15 分鐘（連續查到 1 筆 `outcome=locked` 且 `attempted_at`
  在 15 分鐘內即拒絕）

**理由**：
- 不需要 Redis 與其分散式 token bucket；DB 簡單可審計（同時是稽核資料源）
- ±1 次的精準度可接受（多 instance 偶爾競爭，但 lock 一旦寫入就生效）
- Index `(lower_email, attempted_at)` 即可在 200ms 內完成查詢

**已評估**：
- Sliding window / token bucket on Redis：精確但引入新依賴
- IP-based rate limit：本階段不採用（避免 NAT 後合法使用者被連坐）；
  未來可加為第二維度

---

## 5. 邀請連結 token 格式與生命週期

**決策**：
- 明文：`invite_` + 32 byte URL-safe base64 隨機
- DB 僅存 SHA-256 指紋（同 Phase 1 credential 模式）
- 48 小時 expiry；單次有效（`used_at` 一旦非 null 即不可重用）
- URL 形式：`https://<base>/auth/invitation/<token>`，由管理員拷貝給對方

**理由**：
- 重用 Phase 1 credential 設計，學習成本為零
- 48 小時兼顧「合理人類使用時間」與「短到防外洩」
- 純 URL 不需 email 寄送，正好對齊「無 SMTP」決策

**已評估**：
- JWT：簽章便利但難撤銷；overkill
- 短期 UUID v4：熵足夠但無 prefix 不利眼識別

---

## 6. Cookie + CSRF

**決策**：
- 認證後改動性 admin/me 端點以 **double-submit cookie** 為 CSRF 保護
  （`aiapi_csrf` cookie + `X-CSRF-Token` header 必須相符）
- 純 OAuth callback / login 不需 CSRF（state 已是 CSRF token）

**理由**：
- `SameSite=Lax` 已擋大多數 CSRF，但 cross-site `POST` 仍可能；double-submit
  是無 server-state 的最簡保護
- 對 API 客戶端友善（前端只需 echo cookie 值到 header）

**已評估**：
- 加密 CSRF cookie：較複雜，現階段不需要
- 純依賴 `SameSite=Lax`：對較舊瀏覽器或被夾在跨站 iframe 情境下不安全

---

## 7. Google Cloud Console 設定（plan 階段需給使用者的清單）

於 [console.cloud.google.com](https://console.cloud.google.com) 建立 OAuth
2.0 Client ID（type: Web application），設定：

| 欄位 | 值 |
|---|---|
| Authorized JavaScript origins | `http://localhost:8000`、`https://ai-api.dev.internal`、`https://ai-api.<prod-domain>` |
| Authorized redirect URIs | `<上述各 base>/auth/oidc/callback` |
| Brand restriction | 設為組織內 Google Workspace 網域（可選但建議） |

產出兩個值：`client_id` 與 `client_secret`，提供給 `.env` / K8s Secret。

---

## 8. 既有資料 migration（subject 字串 → Member FK）

**決策**：以 Alembic data migration 在 `0002_auth_membership.py` 內：

1. 建所有新表（members、sessions、…）
2. 對 `allocations` 加欄位 `member_id` (nullable 暫時)、`subject_snapshot`
3. **data migration**：
   - 從 `allocations` SELECT DISTINCT `subject`
   - 對每個 subject 字串：
     - INSERT INTO members (id=ULID, email=lower(subject) if 看似 email else
       NULL, external_id=subject, provider='external', status='active',
       display_name=subject, created_by='migration')
     - UPDATE allocations SET member_id=<new>, subject_snapshot=subject
       WHERE subject=<value>
4. 加 `NOT NULL` 約束到 `member_id`
5. DROP `allocations.subject`（保留 `subject_snapshot` 供稽核）

**理由**：
- Zero downtime（雖然非滾動式但 INSERT/UPDATE 在小規模下 ms 級）
- `external_id=subject` 確保任意字串都有歸屬，不丟資料
- 保留 `subject_snapshot` 呼應 audit need；FR-021 要求行為一致 → 由 service
  層持續寫入 snapshot 即可

**已評估**：
- Drop `subject` 不保留：違反審計可追溯精神
- 保留 `subject` 與 `member_id` 並存：永遠分叉，技術債

---

## 9. 認證 middleware vs Depends

**決策**：以 FastAPI **Dependency Injection** (`Depends(require_member)`
等) 表達認證，**不**用 middleware 全域強制。

**理由**：
- 公開端點（healthz、Google OIDC start/callback、`/auth/invitation/{token}`）
  與保護端點都明確聲明，避免 middleware 漏網
- 與 Phase 1 既有 `require_admin_token` 一致
- 測試時可以 dependency_overrides 注入假身份

**已評估**：
- 全域 middleware + decorator allow-list：容易漏設、難測

---

## 10. Email 標準化

**決策**：所有 email 儲存與比對皆以 `email_validator.validate_email(...).normalized.lower()`

**理由**：
- 處理 IDN、加號變體、大小寫一致
- DB UNIQUE 索引建在 `lower(email)` 上

---

## 11. NEEDS CLARIFICATION 解決狀態

spec.md 與 plan.md 中所有 NEEDS CLARIFICATION 均已決策；剩餘細節（欄位、
路徑、錯誤碼）見 `data-model.md` 與 `contracts/openapi.yaml`。
