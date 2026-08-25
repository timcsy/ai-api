# Feature Specification: 第一方網頁 app 以 OAuth（Authorization Code + PKCE）領取 API 金鑰

**Feature Branch**: `057-oauth-authorization`
**Created**: 2026-08-25
**Status**: Implemented (back-filled — 程式碼先於本規格建立並測試；本文件回填以納入 speckit 流程)
**Input**: User discussion: 「可以再更多聊聊 OAuth 機制嗎？」→ 定案「主要是網頁 app、first-party 就好、金鑰長期即可」

## 背景與問題

維護者想寫自己的（第一方）網頁應用,讓它們**連到本平台領取 gateway API 金鑰**,而不是靠管理員手動建金鑰再貼上。現有的 device flow（RFC 8628，spec 029/Codex）已是「app 領鑰」的一種 OAuth,但**它是為 CLI/原生 app 設計的輪詢式流程**;網頁 app 的自然體驗是**瀏覽器導轉式**的 Authorization Code。

本功能新增 **OAuth 2.0 Authorization Code + PKCE** 流程,讓第一方網頁 app 把（已登入的）成員導轉到本平台同意頁,成員勾選要授權的配額後,app 取回一個一次性 code,再換成一把**長期有效的 `Credential`**（即系統既有、可撤回、有範圍、會計費的金鑰）。OAuth 只是「發鑰的 UX」,不另立權限或計費模型。

**範圍決策（維護者定案,已凍結）**：
- **只做網頁 app 的 Authorization Code + PKCE**（device flow 續留給 CLI/原生）。
- **First-party only**：不做第三方 client 註冊/`client_secret`;靠「成員登入 + 同意」+ **`redirect_uri` 白名單** 當關卡。**不要求 client_secret**(這樣純 SPA 也能接)。
- **長期金鑰**：發出的是既有 `Credential`,撤回前有效;**不做 refresh token**。
- 一條流程同時涵蓋「app 有後端」與「純 SPA 無後端」（PKCE 兩者皆適用）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 網頁 app 領到可用金鑰（Priority: P1）

第一方網頁 app 把已登入成員導到 `/oauth/authorize`;成員勾選配額、按核准;app 的 callback 收到 code,換成金鑰,之後拿它打 `/v1/*`。

**Why this priority**：這是本功能的核心價值。

**Independent Test**：以 PKCE 走完 consent→approve→token,拿到 `access_token`（以 `aiapi_` 開頭）+ `credential_id`;該金鑰即既有 Credential，綁定勾選的 allocation。

**Acceptance Scenarios**:
1. **Given** 成員已登入且有 active allocation,**When** app 帶合法參數導到同意頁、成員勾配額核准,**Then** 導回 `redirect_uri?code=…&state=…`;app `POST /oauth/token`(帶 `code_verifier`)換得金鑰。
2. **Given** 同一個 code,**When** 第二次拿去換,**Then** 400 `invalid_grant`(一次性)。

### User Story 2 - 成員能看到並撤回已授權的 app（Priority: P2）

發出的金鑰在成員的「應用金鑰」清單以 app 名(`client_name`)顯示,可隨時撤回。

**Why this priority**：長期金鑰必須可控;沿用既有 Credential 清單即滿足。

**Independent Test**：OAuth 換得的金鑰出現在成員金鑰清單、可撤回;撤回後打 `/v1/*` 失效。

### Edge Cases（安全,mandatory）
- `redirect_uri` **不在白名單** → consent 直接 400 `redirect_uri_not_allowed`(fail-closed;白名單空=一律拒)。
- **PKCE 驗證失敗**(`code_verifier` 對不上 `code_challenge`) → token 400 `invalid_grant`。
- **`redirect_uri` 在換 token 時與 consent 不符** → 400 `invalid_grant`。
- **code 過期**(核准後 >120s)→ 400 `invalid_grant`。
- **未登入** 呼叫 consent/approve → 401/403。
- 成員只能授權**自己的** allocation(他人 allocation → `invalid_scope`)。
- 拒絕 → 導回 `redirect_uri?error=access_denied&state=…`。

## Requirements *(mandatory)*

- **FR-001**：提供 `POST /oauth/token`(公開,無 session)以 authorization code + PKCE `code_verifier` 換取金鑰;回 `{access_token, token_type:"bearer", credential_id, scope}`。
- **FR-002**：提供成員端(session-authed)`POST /me/oauth/consent`(登記 + 驗 `redirect_uri` 白名單 + 驗 PKCE method)、`GET /me/oauth/{id}`、`POST /me/oauth/{id}/approve`(勾 allocation → 發 code)、`POST /me/oauth/{id}/deny`。
- **FR-003**：PKCE **S256 強制**;`code_challenge_method != S256` → 拒。
- **FR-004**：`redirect_uri` **前綴白名單**(env `OAUTH_REDIRECT_ALLOWLIST`);空 ⇒ 一律拒。
- **FR-005**：authorization code **一次性 + 短 TTL(120s) + 綁 `redirect_uri` 與 `code_challenge`**;consent 視窗 TTL 600s。
- **FR-006**：核准當下**只發 code、不建金鑰**;金鑰在 token 交換時才由既有 `create_member_credential` 建立(綁勾選的 allocation)。
- **FR-007**：`state` 由 app 提供、原封導回(CSRF)。
- **FR-008**：發出的金鑰為既有 `Credential`(可撤回、有範圍、計費),以 `client_name` 標示來源、顯示於成員金鑰清單。
- **FR-009**：不要求 `client_secret`;不發 refresh token。

## Assumptions（凍結）
- First-party only;安全靠 session+同意+PKCE+redirect 白名單,不做第三方 client 註冊。
- 長期金鑰;不做 refresh/輪替(未來可加金鑰到期日,非本功能)。
- 金鑰放哪(SPA vs app 後端)由各 app 自行決定,流程一致。

## 非目標
- 第三方 app 生態、client 註冊、client_secret、refresh token、scope 到「單一模型」以下的細分(目前 scope = 勾選的 allocation 集合)。
