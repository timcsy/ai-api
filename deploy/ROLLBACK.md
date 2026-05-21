# 回滾 Runbook

對應 spec.md FR-018、SC-006：任一次失敗更新可在 5 分鐘內回到前一可用版本。

## 偵測更新失敗

更新後觀察：

```bash
kubectl -n <namespace> rollout status deploy/<release>-ai-api --timeout=2m
kubectl -n <namespace> get pods -l app.kubernetes.io/instance=<release>
```

若 readiness probe 持續失敗、pods CrashLoopBackOff，或健康檢查回應異常，
即進入回滾流程。

## 回滾步驟

### 1. 確認 Helm release 與歷史

```bash
helm -n <namespace> history <release>
```

選擇要回到的 revision（通常是上一個成功的）。

### 2. 執行回滾

```bash
helm -n <namespace> rollback <release> <previous-revision>
```

此命令會：
- 重新套用前一版的 manifests
- 觸發新一輪 rolling update
- migration Job 設為 `pre-upgrade` hook，會在每次 rollback 重跑（idempotent）

### 3. 驗證

```bash
kubectl -n <namespace> rollout status deploy/<release>-ai-api
kubectl -n <namespace> port-forward svc/<release>-ai-api 8000:80 &
curl -s localhost:8000/healthz   # 應回 {"status":"ok"}
```

並執行 quickstart §3 的撤回測試以確認核心功能可用。

## 何時需要手動釘版本

若 Renovate PR 引入了破壞性 LiteLLM 升級，CI 沒擋住但生產出現問題：

1. 在 `values.yaml` 中明確指定上一個可用 image tag
2. 開新 PR，標記 `do-not-merge` 至原本的 Renovate PR
3. 在 issue 中記錄該版本的問題、最低支援版本

## SLO 量測

於開發叢集執行：

```bash
# 故意升級到不存在 tag
helm -n ai-api upgrade ai-api ./deploy/helm/ai-api \
    --reuse-values --set image.tag=does-not-exist

# 等 readiness 失敗
sleep 60

# 計時回滾
time helm -n ai-api rollback ai-api
time kubectl -n ai-api rollout status deploy/ai-api-ai-api --timeout=5m
```

紀錄回滾耗時，必須 ≤ 5 分鐘。
