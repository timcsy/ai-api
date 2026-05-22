# Phase 0 Research: 階段 2.5 — Hardening

---

## 1. Provider 字串解析規則

**決策**：採用 LiteLLM 既有慣例 — `<provider>/<model>`，無 `/` 即視為預設
provider（首階段為 `azure`）。

**實作**：
```python
def parse_provider(model: str, default: str = "azure") -> tuple[str, str]:
    if "/" in model:
        prov, _, rest = model.partition("/")
        return prov.lower(), rest
    return default, model
```

**理由**：對齊 LiteLLM 文件，使用者不需學新 syntax。

**已評估**：
- 自定 `provider:` 前綴：破壞 LiteLLM 範例可移植性
- 由 settings 同時管 model→provider 對應表：YAGNI；分配本來就指定 model

---

## 2. NetworkPolicy 設計

**決策**：Helm chart 內建一份 `templates/networkpolicy.yaml`，**預設 enabled**，
策略：

```yaml
egress:
  - to: [{ ipBlock: { cidr: 0.0.0.0/0, except: [169.254.0.0/16, 10.0.0.0/8] } }]
    ports: [{ protocol: TCP, port: 443 }]
  - to: [{ namespaceSelector: { matchLabels: { ns: kube-system } } }]
    ports: [{ protocol: UDP, port: 53 }]
  - to: [{ podSelector: { matchLabels: { app: ai-api-pg } } }]
    ports: [{ protocol: TCP, port: 5432 }]
ingress:
  - from: [{ namespaceSelector: {} }]
    ports: [{ protocol: TCP, port: 8000 }]
```

**理由**：
- 對 internet 443 開放是 LLM 供應商可達性的最小妥協（CIDR allowlist 不可行
  — 雲端供應商 IP 範圍會變）
- `except: [10.0.0.0/8]` 預設排除 RFC1918；如果使用者的 Postgres 在 10.x，
  另寫 podSelector 規則允許
- `169.254.0.0/16` 全段排除（AWS / GCP / Azure metadata IMDS 都在此段）

**已評估**：
- Cilium FQDN policy：精準但需換 CNI（assumptions §1）
- Envoy sidecar：多一個元件，spec FR-024 已排除

---

## 3. Trivy 整合方式

**決策**：CI workflow 內以 `aquasecurity/trivy-action@v0.24.0`（pinned tag）
掃描 image。

```yaml
- name: Trivy scan
  uses: aquasecurity/trivy-action@v0.24.0
  with:
    image-ref: ghcr.io/timcsy/ai-api:${{ github.sha }}
    severity: HIGH,CRITICAL
    exit-code: '1'
    ignore-unfixed: true
    trivyignores: .trivyignore
```

**理由**：
- pinned tag 防止 supply-chain 替換（呼應 experience「mutable tag」教訓）
- `ignore-unfixed: true` 避免被尚無 patch 的 CVE 卡住，只擋住已有修法的
- `.trivyignore` 在 repo 中明示哪些 CVE 被忽略，PR 描述需附理由

**已評估**：
- Grype：等效，但 GitHub Action 整合稍弱
- Snyk：付費
- 跑 Trivy 在 push to main 而非 PR：失去「擋住合併」的價值

---

## 4. Anomaly detector：CronJob vs 主 process 內 task

**決策**：**K8s CronJob**，每 5 分鐘觸發一次 `python -m ai_api.cli.run_anomaly_detector`，
單次掃描即退出。

**理由**：
- 與 app pod 解耦：app crash 不影響偵測；偵測 bug 不影響線上請求
- 不需引入 process-internal scheduler（APScheduler 等）
- Helm chart 控制 CronJob enable/disable，本機開發可直接 `python -m` 跑

**已評估**：
- asyncio task in app process：每個副本都跑 → 重複偵測、競爭寫 audit；
  協調複雜
- Celery / RQ：YAGNI

---

## 5. Anomaly 觸發演算法

**決策**：

```python
def should_quarantine(allocation_id) -> bool:
    last_hour = count_calls(allocation_id, since=now-1h)
    if last_hour < 100:
        return False  # 量太少不觸發
    baseline = avg_calls_per_hour(allocation_id, since=now-24h, excluding=last_hour)
    if baseline == 0:  # cold-start
        return last_hour >= 10000  # 絕對門檻
    return last_hour >= baseline * 10
```

參數來自 `Settings.anomaly_threshold_multiplier` (預設 10)、
`Settings.anomaly_absolute_cold_start` (預設 10000)、
`Settings.anomaly_min_calls` (預設 100)。

**理由**：
- 兩段式（baseline 倍數 + cold-start 絕對門檻）平衡偽陽性與及時止血
- 「min_calls 100」避免低用量分配被個位數抖動觸發

**已評估**：
- 純絕對門檻：對不同分配缺乏因材施教
- 純倍數：cold-start 永遠不觸發，攻擊者剛拿 token 就大量呼叫無人擋

---

## 6. Distroless 切換步驟

**決策**：base image 改 `gcr.io/distroless/python3-debian12:nonroot`（pinned
by digest），entrypoint 為 `["python3", "-m", "uvicorn", "ai_api.main:app",
"--host", "0.0.0.0", "--port", "8000"]`。

**healthcheck**：以純 Python script 在 image 內：
```dockerfile
HEALTHCHECK CMD ["python3", "/app/healthcheck.py"]
```
`healthcheck.py` 內容：用 `urllib.request` 打 `/healthz`，非 200 即 exit(1)。

**理由**：
- distroless 無 shell，HEALTHCHECK CMD 不能用 `shell form`
- nonroot 變體已內建 non-root user（uid 65532）

**已評估**：
- Alpine + apk del everything：仍有 shell，攻擊面大
- chainguard wolfi：等效，授權上稍複雜

---

## 7. readOnlyRootFilesystem 與必要寫入路徑

**決策**：Deployment 加：
```yaml
securityContext:
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]
volumeMounts:
  - { name: tmp, mountPath: /tmp }
  - { name: cache, mountPath: /home/nonroot/.cache }
volumes:
  - { name: tmp, emptyDir: {} }
  - { name: cache, emptyDir: {} }
```

**理由**：
- LiteLLM / httpx 可能寫 `/tmp` 或 `~/.cache`；用 emptyDir 既滿足又無持久
- ALL caps drop 避開 bind <1024 等需求（uvicorn bind 8000 即可）

---

## 8. Per-IP rate limit 演算法

**決策**：擴充 `ratelimit.is_locked()`，新增 `is_ip_locked(ip)` — 查
`password_attempts` 表「同 source_ip 60s 內 outcome ∈ {bad_password,
unknown_email} 計數 ≥ 10」即鎖 15 分鐘。

**理由**：與既有 per-email 同 schema，不需新表；index `(source_ip,
attempted_at)` 加一條即可。

---

## 9. NEEDS CLARIFICATION 解決狀態

無未決。所有 spec 中的 [NEEDS CLARIFICATION] 都收斂為決策。
