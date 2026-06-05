# Quickstart：一鍵安裝 Codex + device-flow 驗收

後端/協定由 pytest 自動化；安裝腳本以**三平台真機**驗。

## 後端 contract（先 Red 後 Green）

- [ ] **authorize**：`POST /device/authorize` → 回 device_code/user_code/verification_uri/expires_in/interval。
- [ ] **pending / slow_down**：未核可前 `POST /device/token` 回 `authorization_pending`；過快再打回 `slow_down`。
- [ ] **owner-isolation**：未登入 `GET/approve` → 401；成員 approve **他人**分配 → 403、不 mint。
- [ ] **approve → 單次交付**：擁有者 `approve {allocation_id}` → 204；`POST /device/token` 回明文 token + credential_id **一次**；再打回 `expired_token`（明文已清）。
- [ ] **可呼叫 + 可撤回**：交付的 token 能成功打 proxy；該憑證出現在 `/me/allocations/{id}/credentials`，撤回後該 token 失效、同分配其他不受影響。
- [ ] **逾時 / 拒絕**：過 `expires_at` → `expired_token`；`deny` 後 → `access_denied`。
- [ ] **安裝端點**：`GET /install/codex.sh`、`/install/codex.ps1` 回非空純文字，含平台 base_url 與 `model_providers.ccsh` / `wire_api="responses"` / `requires_openai_auth` 關鍵字。

## 後端 integration（Postgres）

- [ ] **migration 0016**：`alembic upgrade head` 建出 `device_authorizations`（unique device_code/user_code、FK、enum VARCHAR、tz 欄）；既有 token / proxy / 計費**零回歸**。
- [ ] **全流程**：authorize → approve（mint）→ token 取回 → 打 proxy 成功 → 撤回憑證 → 失效；節流與時效行為正確。

## 三平台真機（手動，SC-006）

對 Windows / macOS / Linux 各做一次：

- [ ] dashboard 複製該 OS 一行指令 → 終端機執行 → 出現授權連結 + user_code。
- [ ] 瀏覽器（已登入）開授權頁 → 選一個分配 → 核可 → 終端機自動完成、印 ✓ 連線成功。
- [ ] **重開新終端機**打 `codex`（零參數、未設任何環境變數）→ 正常對話。
- [ ] Codex 內 `/model` 切換 → 再呼叫仍走本平台（**不打 api.openai.com**）；未開放 model 回清楚訊息而非 401。
- [ ] dashboard「裝置與憑證」看到新憑證（`Codex on <host>`）→ 撤回 → 該台 Codex 失效。

### 機器上「已裝過 Codex」的情境（每個 OS 至少各驗一種）

- [ ] **已裝 CLI**（`codex` 已在 PATH）：跑一行指令 → 腳本**不重裝**（沿用現有 binary）、保留 `config.toml`
      其他設定、只覆寫 `model_provider` + `[model_providers.ccsh]`；授權後新終端機 `codex` 走本平台。
      驗：原本若以個人 OpenAI 帳號登入，裝後預設 provider 切成 `ccsh`、`auth.json` 換成平台金鑰；
      重跑 `codex login` 可切回個人帳號（可逆）。
- [ ] **已裝編輯器擴充**（VS Code / Cursor 的 Codex，與 CLI 共用 `~/.codex/`）：裝後擴充是否也指向本平台、
      可正常呼叫。**未驗證項要如實記錄**（擴充對自訂 provider + api-key 的支援度尚未實機確認）。
- [ ] **用 ChatGPT 帳號登入的 Codex**（Codex 桌面 App、ChatGPT 桌面版內的 Codex、網頁版 chatgpt.com/codex）：
      確認**不適用**（帳號綁定、不讀本地 `config.toml`、無法指向自訂 base_url）——此為預期行為，記錄為「不支援、引導改用 CLI」。

## 前端（vitest + 手動）

- [ ] 授權頁 `/device`：輸入/確認 user_code → 顯示請求摘要 → 選分配 → 核可/拒絕；非本人分配不可選。
- [ ] dashboard「安裝 Codex」卡：依 OS 顯示一行指令、一鍵複製；360px 手機不溢出（沿用階段 16 RWD）。

## 對應成功標準

| 清單 | SC |
|------|----|
| 5 分鐘內、免貼 token、免環境變數裝好 | SC-001 |
| 新終端機零參數可用 | SC-002 |
| 切 model 不脫鉤 | SC-003 |
| 憑證可見可撤回 | SC-004 |
| 逾時不可兌換、非擁有者不可核可 | SC-005 |
| 三平台真機通過 | SC-006 |
| 既有零回歸 | SC-007 |
