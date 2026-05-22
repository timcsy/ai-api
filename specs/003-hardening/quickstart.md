# Quickstart: 階段 2.5 — Hardening

## 0. 先決條件

- Phase 1+2 quickstart 所有先決條件
- 叢集 CNI **必須支援 NetworkPolicy**（k3s 預設 Flannel 不支援；切到 Calico 或
  k3s `--flannel-backend=none --disable-network-policy=false` + Cilium）

## 1. Provider Allowlist（US1）

```bash
# .env 設定
export AI_API_ALLOWED_PROVIDERS='["azure"]'

uv run uvicorn ai_api.main:app --port 8000 &
APP=$!
sleep 3

# 建分配 + 取 token（沿用 Phase 2 流程）
TOKEN=$(...)

# 允許的 provider — 成功
curl -X POST localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"model":"azure/gpt-4o-mini","messages":[{"role":"user","content":"hi"}]}'

# 不允許的 provider — 403 provider_not_allowed
curl -i -X POST localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"model":"anthropic/claude-3","messages":[{"role":"user","content":"hi"}]}'
# 預期：HTTP 403; body 含 "code":"provider_not_allowed"

kill $APP
```

## 2. NetworkPolicy（US2）— 需 K8s

```bash
helm -n ai-api upgrade ai-api ./deploy/helm/ai-api --reuse-values \
  --set networkPolicy.enabled=true

# 進 pod 測試
kubectl -n ai-api exec deploy/ai-api-ai-api -- \
  python3 -c "import urllib.request; urllib.request.urlopen('http://8.8.8.8/', timeout=3)"
# 預期：socket.timeout / ConnectionRefusedError

kubectl -n ai-api exec deploy/ai-api-ai-api -- \
  python3 -c "import urllib.request; urllib.request.urlopen('http://169.254.169.254/', timeout=3)"
# 預期：失敗（metadata 被擋）

kubectl -n ai-api exec deploy/ai-api-ai-api -- \
  python3 -c "import urllib.request; urllib.request.urlopen('https://api.openai.com', timeout=5)"
# 預期：HTTPError 401 或類似（連線通；只是 API 未授權）→ 表示網路允許
```

## 3. Trivy（US3）— CI

```bash
# 本機端可先跑：
trivy image --severity HIGH,CRITICAL --ignore-unfixed ghcr.io/timcsy/ai-api:main

# CI 觸發：開 PR；workflow 內含 Trivy step
gh pr create --title "test: introduce known-CVE" ...
gh pr checks  # 應該看到 Trivy 失敗
```

## 4. Anomaly Detector（US4）

```bash
# 手動跑一次
uv run python -m ai_api.cli.run_anomaly_detector

# 模擬突發用量（測試用）
ALLOC_ID="..."
for i in $(seq 1 200); do
  curl -X POST localhost:8000/v1/chat/completions ... &
done
wait

# 再跑 detector
uv run python -m ai_api.cli.run_anomaly_detector

# 查 allocation 狀態
curl -s localhost:8000/admin/allocations/$ALLOC_ID -H 'X-Admin-Token: ...' | jq .status
# 預期：quarantined

# 試呼叫（應拒）
curl -i -X POST localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"model":"azure/gpt-4o-mini","messages":[]}'
# 預期：HTTP 403; "code":"allocation_quarantined"

# 解除隔離
curl -X POST localhost:8000/admin/allocations/$ALLOC_ID/unquarantine \
  -H 'X-Admin-Token: ...'
```

## 5. Container Hardening（US5）

```bash
docker build -t ai-api:dev -f deploy/docker/Dockerfile .

# 嘗試 shell — 失敗（distroless 無 shell）
docker run --rm -it ai-api:dev sh
# 預期：exec: "sh": executable file not found

# 嘗試啟動 — 應成功
docker run --rm -d -p 8000:8000 --env-file .env ai-api:dev
curl localhost:8000/healthz
# 預期：{"status":"ok"}

# K8s 上驗 readOnlyRootFilesystem
kubectl -n ai-api exec deploy/ai-api-ai-api -- python3 -c "open('/etc/x', 'w')"
# 預期：PermissionError (read-only file system)
```

## 6. per-IP Rate Limit（US6）

```bash
# 同 IP 對 10 個 email 各失敗一次 + 第 11 次
for i in $(seq 1 11); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST localhost:8000/auth/local/login \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"a$i@x.com\",\"password\":\"wrong\"}"
done
# 預期：1~10 → 401；第 11 → 429
```

## 7. SC 檢核表

| SC | 對應步驟 |
|---|---|
| SC-001 | §1 (provider allowlist) |
| SC-002 | §2 (NetworkPolicy 四種情境) |
| SC-003 | §3 (Trivy CI) |
| SC-004 | §4 (Anomaly + quarantine) |
| SC-005 | §6 (per-IP rate limit) |
| SC-006 | §5 (distroless + readOnlyRootFilesystem) |
| SC-007 | `uv run pytest -q`（全 Phase 1+2 regression 綠） |
| SC-008 | `git log -- tests/ src/`（test commit 早於 impl commit） |
