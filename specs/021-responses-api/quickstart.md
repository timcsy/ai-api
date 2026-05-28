# Quickstart: 用 Codex 連本平台

**Branch**: `021-responses-api`

驗證 SC-001/005——開發者把 Codex 指向平台、用分配憑證跑 agent 任務。

## 前置

- 一張有效的平台分配憑證（allocation token），其綁定模型支援 responses
  （`capabilities` 含 `responses`，例：Azure 的 reasoning 模型）。
- 已安裝 Codex CLI。

## Codex 設定（`~/.codex/config.toml`）

```toml
model = "<平台模型 slug>"
model_provider = "ccsh"

[model_providers.ccsh]
name = "CCSH AI Gateway"
base_url = "https://ai-ccsh.tew.tw/v1"
wire_api = "responses"
env_key = "CCSH_AI_TOKEN"
```

```bash
export CCSH_AI_TOKEN="<allocation-token>"
codex "在這個 repo 新增一個 hello world 並跑起來"
```

## 預期

- 回應即時逐步顯示（串流不卡整段）。
- 含工具呼叫（讀寫檔）的多輪任務能完成。
- 平台用量總覽出現該次呼叫，歸戶到該分配，花費含 reasoning / cached 分項。

## 手動煙霧測試（不經 Codex，純 curl）

```bash
# 非串流
curl -sS https://ai-ccsh.tew.tw/v1/responses \
  -H "Authorization: Bearer $CCSH_AI_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"<slug>","input":"say hi"}'

# 串流（應逐步吐 SSE 事件）
curl -N https://ai-ccsh.tew.tw/v1/responses \
  -H "Authorization: Bearer $CCSH_AI_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"<slug>","input":"count to 5","stream":true}'
```

## 驗收對照

| 檢查 | 對應 |
|------|------|
| Codex 多輪 + 工具 + 推理完成 | SC-001 |
| 用量歸戶 + 四類 token 分項 | SC-002 |
| 多 provider 皆可呼叫 | SC-003 |
| store / previous_response_id 接續 + 歸屬隔離 | SC-004 |
| 串流即時、無緩衝逾時 | SC-005 |
| 撤回即拒、斷線仍記用量 | SC-006 |
| 無 provider key 外洩 | SC-007 |

## 部署注意（SSE 不緩衝）

- frontend nginx 對 `/v1/responses` 須 `proxy_buffering off`。
- Traefik ingress 確認不緩衝 SSE。
- 真機驗證前先 `curl -N` 確認串流逐步抵達（非一次吐完）。
