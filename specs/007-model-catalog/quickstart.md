# Quickstart: 階段 4 — Model Catalog

## 0. 先決條件

- Phase 1 已上線（任何 active member 已可登入）
- migration 0006 已 apply

## 1. 啟服務 + migration

```bash
uv run alembic upgrade head      # 0006_model_catalog
uv run uvicorn ai_api.main:app --port 8000 &
```

## 2. 載入首版 YAML（US4）

```bash
uv run python -m ai_api.cli.load_models deploy/catalog/azure-2026-05.yaml
# 預期：loaded: inserted=9 updated=0
```

再跑一次驗證 idempotent：

```bash
uv run python -m ai_api.cli.load_models deploy/catalog/azure-2026-05.yaml
# 預期：loaded: inserted=0 updated=9 (updated_at refreshed)
```

## 3. Browse + Filter（US1 + US2）

先登入取得 session cookie（既有 Phase 2 流程；測試時可用 `--cookie-jar`）：

```bash
COOKIE='ai_api_session=<paste-from-browser-or-test>'

# 全部 active
curl -s "localhost:8000/catalog/models" -H "Cookie: $COOKIE" | jq 'length'
# → 9

# 只看 image 輸出
curl -s "localhost:8000/catalog/models?modality_output=image" -H "Cookie: $COOKIE" | jq '.[].slug'
# → "azure/dall-e-3"

# vision + function-calling + 低成本（US2 SC-002）
curl -s "localhost:8000/catalog/models?capability=vision&capability=function-calling&cost_tier=low" \
  -H "Cookie: $COOKIE" | jq '.[].slug'
# → "azure/gpt-4o-mini" （唯一命中）

# 含 deprecated
curl -s "localhost:8000/catalog/models?include_deprecated=true" -H "Cookie: $COOKIE" | jq 'length'

# context window > 100K
curl -s "localhost:8000/catalog/models?min_context_window=128000" -H "Cookie: $COOKIE" | jq '.[].slug'
```

## 4. Detail + example_request（US1）

```bash
curl -s "localhost:8000/catalog/models/azure%2Fdall-e-3" -H "Cookie: $COOKIE" | jq .example_request
# 預期：含 curl 字串 + body JSON 範例
```

## 5. Facet API（US3）

```bash
curl -s "localhost:8000/catalog/filters" -H "Cookie: $COOKIE" | jq
# 預期：
# {
#   "modality_input": {"text": 9, "image": 2, "audio": 1},
#   "modality_output": {"text": 7, "image": 1, "audio": 1, "embedding": 2},
#   "capabilities": {"chat": 4, "vision": 2, ...},
#   "cost_tier": {"low": 4, "medium": 3, "high": 2},
#   "recommended_for": {...},
#   "family": {"gpt-4": 2, "o-series": 2, ...},
#   "tags": {...}
# }
```

驗證穩定 schema：刪空 DB 後再跑，dimension key 集合應該完全相同（雖然 value 都是 {}）。

## 6. Deprecation（US5）

```bash
# 編輯 YAML，把 azure/whisper-1 改成 status: deprecated
# deprecation_note: "Azure Whisper API 將於 2027-01 停服，請改用 azure/whisper-v2"
uv run python -m ai_api.cli.load_models deploy/catalog/azure-2026-05.yaml

# 預設列表不再回 whisper
curl -s "localhost:8000/catalog/models" -H "Cookie: $COOKIE" | jq '[.[] | select(.slug=="azure/whisper-1")] | length'
# → 0

# 但 detail 仍可查
curl -s "localhost:8000/catalog/models/azure%2Fwhisper-1" -H "Cookie: $COOKIE" | jq .deprecation_note
# → "Azure Whisper API 將於 2027-01 停服..."

# 含 deprecated
curl -s "localhost:8000/catalog/models?include_deprecated=true" -H "Cookie: $COOKIE" | jq 'length'
```

## 7. 未登入 / 失能 member 行為

```bash
# 無 cookie
curl -s -o /dev/null -w "%{http_code}\n" "localhost:8000/catalog/models"
# → 401

# 用 disabled member 的 session
curl -s -H "Cookie: ai_api_session=<disabled-member-session>" \
  -o /dev/null -w "%{http_code}\n" "localhost:8000/catalog/models"
# → 403
```

## 8. SC 檢核

| SC | 對應步驟 |
|---|---|
| SC-001 | §2 YAML 含 9 個模型 |
| SC-002 | §3 vision+fn-calling+low 命中 1 |
| SC-003 | §5 facet schema 在空/有資料兩態相同 |
| SC-004 | §2 idempotent（第二次跑無錯誤） |
| SC-005 | §6 deprecated 隔離 |
| SC-006 | `uv run pytest -q` 167 + 新增測試全綠 |
| SC-007 | `git log -- tests/ src/` 順序 |
