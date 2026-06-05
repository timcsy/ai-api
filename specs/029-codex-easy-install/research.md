# Research：一鍵安裝 Codex + device-flow

## 1. device-flow 協定設計（RFC 8628 改寫）

- **Decision**：採 RFC 8628 Device Authorization Grant 的**形狀**（device_code + user_code + 輪詢），但以**平台既有 session 登入**作為「使用者已認證」來源，不引入 OAuth client/scope/token endpoint 全套。三個公開動作 + 三個 member 動作：
  - `POST /device/authorize`（公開，CLI 起手）→ 回 `device_code`（高熵不透明）、`user_code`（短、人類可讀，如 `ABCD-EFGH`）、`verification_uri`（`/device`）、`verification_uri_complete`（`/device?code=ABCD-EFGH`）、`expires_in`（600s）、`interval`（5s）。
  - `GET /me/device/{user_code}`（member session）→ 回該待授權請求摘要（裝置名提示、建立時間），供授權頁顯示。
  - `POST /me/device/{user_code}/approve`（member session）→ body `{allocation_id}`；驗擁有者 → mint 一把 per-device 憑證 → 把**明文加密暫存**在該列、狀態轉 `approved`。
  - `POST /me/device/{user_code}/deny`（member session）→ 狀態轉 `denied`。
  - `POST /device/token`（公開，CLI 輪詢）→ body `{device_code}`；依狀態回 `authorization_pending` / `slow_down` / `expired_token` / `access_denied` / 成功時回 `{token, token_prefix}` 並**清除暫存明文**（單次交付）。
- **Rationale**：CLI 與瀏覽器是兩個 channel，token 必須經輪詢交付；user_code 讓成員不必在 CLI 與瀏覽器間複製長字串。沿用 session 省掉自建 OAuth 的複雜度（YAGNI）。
- **Alternatives**：① 完整 OAuth2 device grant（含 client 註冊）——過重，違反 YAGNI；② 直接在 CLI 開 localhost 回呼（loopback redirect）——非技術成員防火牆/瀏覽器情境不穩，且要 CLI 起 server；③ 純貼 token（階段 18 已可）——保留為 fallback，不是主路徑。

## 2. 明文 token 的單次交付（hash-only 的有界例外）

- **Decision**：mint 憑證時平台只存 fingerprint（不變），但 device-flow 需把明文交給輪詢的 CLI。故在 `device_authorizations` 列上以 **Fernet 加密**暫存明文，欄位 `encrypted_token`；`POST /device/token` 成功交付後**立即清為 NULL**（單次）。逾時/清理任務也會清掉。復用既有 `PROVIDER_KEY_ENC_KEY` 同款 Fernet 基建。
- **Rationale**：兩 channel 交付的物理必要；以「加密 + 單次 + 即清 + 短時效」把暴露面壓到最小，符合原則 1 精神（明文不長存、不可重取）。
- **Alternatives**：① 明文明碼存 DB——否（違反 hash-only 精神）；② approve 時直接把明文塞回瀏覽器讓成員貼到 CLI——又回到「複製貼上 token」，違反本功能目的；③ 不存、approve 與 poll 同步阻塞等待——HTTP 長連線不可靠、難跨重啟。

## 3. Codex 設定「不脫鉤」（真機已驗結論）

- **Decision**：`config.toml` 以 **merge-style** 寫入一個自訂 provider 區塊並設為預設：
  ```toml
  model_provider = "ccsh"
  [model_providers.ccsh]
  name = "CCSH"
  base_url = "<平台>/v1"
  wire_api = "responses"
  requires_openai_auth = true
  # 真機驗：關閉 websocket 消除 405 噪音
  ```
  憑證走 `printf '%s' "<token>" | codex login --with-api-key`（寫 `~/.codex/auth.json`）→ 零環境變數。
- **Rationale**：真機驗證（Windows，bat v1–v5）確認自訂 provider `ccsh` 在 `/model` 切換後**存活**（Codex 重寫 model 但保留 `model_providers`），`requires_openai_auth=true` 讓它用 auth.json 而非 env，`supports_websockets=false` 殺掉 WS 405 紅字；Codex 是 Rust 獨立 binary（GitHub Releases）→ 免 Node。
- **Alternatives**：唯讀 config / wrapper / 別名——使用者明確排除，且脆弱。

## 4. 安裝腳本的取得與跨平台

- **Decision**：平台端點 `GET /install/codex.sh`、`GET /install/codex.ps1` 回**純文字腳本**，由後端把 `base_url` 注入（不在前端硬編）。dashboard 顯示一行指令：
  - macOS/Linux：`curl -fsSL <平台>/install/codex.sh | sh`
  - Windows：`irm <平台>/install/codex.ps1 | iex`
  腳本流程：偵測 OS/arch → 下載對應 Codex binary 到使用者目錄並加進 PATH → 寫 `config.toml`（merge）→ 跑 device-flow（呼叫 authorize、印 user_code + 授權網址、輪詢 token）→ `codex login --with-api-key` → 跑一次測試呼叫顯示 ✓。
- **Rationale**：一行指令是最低摩擦；後端注入 base_url 確保正確；binary 直download 免 Node。
- **Alternatives**：npm 全域安裝（要 Node，門檻高）；GUI 安裝程式（維護成本高、跨平台難，YAGNI）。
- **Risks/經驗**：`.bat`/PowerShell 中英混排易亂碼（真機已遇）→ 腳本訊息以英文為主、中文另行；Gatekeeper/防毒攔截下載 → 腳本輸出白話指引。三平台**真機驗收**不可省（經驗：Codex 行為真機才暴露）。

## 5. 節流、時效、單次（防濫用）

- **Decision**：`device_code` ≥128-bit 不透明；`user_code` 8 字 base32 去混淆字元、格式化 `XXXX-XXXX`、**全域唯一且短時效**。輪詢：記 `last_polled_at`，若間隔 < `interval` 回 `slow_down`；過 `expires_at` 回 `expired_token`；成功/拒絕後該列終結（單次）。逾時列由背景清理（或惰性過期判定）。
- **Rationale**：對齊 RFC 8628 安全建議；user_code 短到可口述但配短時效限制暴力猜測窗。
- **Alternatives**：長 user_code（難輸入）；無節流（可被當開放輪詢濫用）。

## 6. 與階段 18 的接點

- **Decision**：mint 直接呼叫 `AllocationService.add_credential(allocation, name)`（已存在），`name` 預設 `Codex on <hostname>`（由 CLI 在 authorize 帶上裝置提示）。憑證自動進「裝置與憑證」清單、可撤回/rotate（US4 免額外前端）。
- **Rationale**：零重工、行為一致（撤一把不連坐、就地 rotate）。
- **Alternatives**：另造一種「device 憑證」——多餘，違反 YAGNI 與原則 1（單位是分配）。

## 未解項

- 無 `NEEDS CLARIFICATION`。`verification_uri_complete` 是否預填 user_code（便利但略降安全）採「預填、但仍需登入 + 明確按核可」折衷。
