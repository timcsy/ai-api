# AI API Manager

組織內部 AI API 的**單一分流入口**：用一套 OpenAI 相容的閘道，把多家 AI 供應商
（Azure OpenAI / OpenAI / Anthropic / Gemini）統一對成員開放，並以**可撤回的分配憑證**
管控誰能用、用多少、花多少——用量與成本全部統一歸戶。

> 核心理念：**分享就是資源的分配**。每一筆 AI 存取都是一份有對象、有額度、可調整、
> 可收回的資源，而不是一次性把 key 發出去。

## 功能總覽

- **OpenAI 相容代理**
  - `POST /v1/chat/completions`（Chat Completions）
  - `POST /v1/responses`（Responses API，**支援 SSE streaming、工具呼叫、reasoning**）
    — 讓 **OpenAI Codex** 等 agent CLI 用平台憑證即可使用
- **多供應商**：經 `litellm`（library form）統一抽象；OpenAI/Azure 原生高保真、其他家自動橋接
- **可撤回分配憑證**：每筆分配發行獨立 token；撤回後即時生效（不等過期），也可**暫停 / 恢復**
- **身份與成員管理**：Google Workspace SSO + 本機密碼；白名單 / 自動註冊規則 / 來源限制
- **模型目錄**：以「模型」為第一公民，多面向 filter；可見性 = 已配置 credential ∩ 存取政策
- **Tag-based 存取規則**：用 tag 批次授權；新成員可依規則自動貼 tag
- **自助領取憑證**：被授權的成員可對開放的 model 一鍵領取；亦可自助暫停/恢復自己的憑證
- **用量觀測與計費**：point-in-time 計費，分項記錄 input / output / **reasoning / cached** token；
  月度配額、自適應配額池、CSV/JSON 匯出
- **管理員 Web UI**：成員、分配、用量、配額、價目、Provider 憑證、稽核紀錄
- **安全加固**：Provider key 以 Fernet 加密落 DB（金鑰由 K8s Secret 提供，pod 啟動即驗證）、
  K8s NetworkPolicy、CI Trivy 掃描 + SBOM、distroless runtime

## 架構

- **後端**：FastAPI（Python 3.11+）+ SQLAlchemy 2.x async + Alembic；上游經 `litellm` library form
- **前端**：React 19 + Vite 6 + TypeScript（strict）+ shadcn/ui + TanStack Query
- **資料庫**：PostgreSQL（生產）/ SQLite（dev、CI）
- **部署**：Kubernetes + Helm chart（`deploy/helm/ai-api`）；前端為單一來源 nginx 反向代理到後端
- **映像**：後端 distroless、前端 unprivileged nginx；CI 以 GitHub Actions build + Trivy 把關

## 對外 API

把 `$TOKEN` 換成你分配到的憑證，放在 `Authorization: Bearer`。

```bash
# Chat Completions
curl -X POST https://<host>/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"model":"azure/gpt-4o","messages":[{"role":"user","content":"你好"}]}'

# Responses（含串流）
curl -N -X POST https://<host>/v1/responses \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"model":"azure/gpt-5.4","input":"你好","stream":true}'
```

### 搭配 OpenAI Codex

支援 `responses` 能力的模型可在後台「模型目錄 → 如何呼叫 → Codex」分頁**下載 `config.toml`**
並依各作業系統步驟設定。基本設定：

```toml
# ~/.codex/config.toml
model = "azure/gpt-5.4"
model_provider = "ccsh"

[model_providers.ccsh]
name = "CCSH AI Gateway"
base_url = "https://<host>/v1"
wire_api = "responses"
env_key = "CCSH_AI_TOKEN"
```

```bash
export CCSH_AI_TOKEN="$TOKEN"
codex "在這個資料夾建一個 hello.py 並執行"
```

## 本機開發

需要 Python 3.11+、[uv](https://github.com/astral-sh/uv)、Node.js（前端）、一個 Postgres。

```bash
# 後端
export DATABASE_URL=postgresql+asyncpg://aiapi:aiapi@localhost:5432/aiapi
uv sync
uv run alembic upgrade head
uv run uvicorn ai_api.main:app --reload --port 8000

# 前端（另一個終端）
cd frontend
npm install
npm run dev
```

詳細環境變數與首位管理員設定見 [`docs/deployment.md`](./docs/deployment.md)。

## 測試與檢查

```bash
# 後端：單元 + 契約（Docker-free，in-memory/temp SQLite）
uv run pytest tests/unit tests/contract
uv run pytest            # 含整合測試（需 Docker / Postgres）
uv run ruff check . && uv run mypy src/ai_api

# 前端
cd frontend && npm run lint && npm run typecheck && npm test
```

## 部署

Kubernetes / Helm 部署、必填機密、首位管理員 bootstrap、Responses/Codex 與 SSE 不緩衝
等注意事項，詳見 [`docs/deployment.md`](./docs/deployment.md)。

## 文件

- 工程憲章：[`.specify/memory/constitution.md`](./.specify/memory/constitution.md)
- 領域原則：[`knowledge/principles.md`](./knowledge/principles.md)
- 願景與路線圖：[`knowledge/vision.md`](./knowledge/vision.md)
- 經驗教訓：[`knowledge/experience.md`](./knowledge/experience.md)
- 設計文件：[`knowledge/design/`](./knowledge/design/)
- 功能規格（spec / plan / tasks）：[`specs/`](./specs/)
- 部署指南：[`docs/deployment.md`](./docs/deployment.md)

## 開發流程

本專案採 spec-driven 開發（spec → plan → tasks → 失敗測試 → 實作 → 重構 → 審查 → 合併），
並強制 TDD 與契約優先；規格文件一律繁體中文、程式識別字英文。詳見工程憲章。
