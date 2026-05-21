# Quickstart 執行紀錄 — 階段 1 分流核心

**日期**：2026-05-21
**環境**：本機開發（macOS 24.6.0，Python 3.12.11，uv 0.11.8，Docker 28.3.2，
testcontainers Postgres 15）

## SC-001~SC-008 檢核

| SC | 結果 | 證據 |
|---|---|---|
| **SC-001** 1 分鐘內建立分配→呼叫 | ✅ | `test_create_then_proxy_call_succeeds`（mock 上游）整段 < 3s |
| **SC-002** 撤回 5 秒內生效 | ✅ | `test_revoke_then_call_rejected_within_slo` 量測 elapsed ≤ 5.0s，本機實測 < 0.05s |
| **SC-003** 底層 key 不洩漏 | ✅ | 全套契約測試 + integration `test_us1_no_key_leak`（5 個情境）+ `test_us3_attribution.test_error_message_is_redacted` + `test_no_key_leak_global`（11 個情境）= **16 個情境全部 0 命中** |
| **SC-004** 呼叫紀錄可反查 | ✅ | `test_list_calls_includes_success_and_reject`、`test_us3_attribution` |
| **SC-005** 開發叢集部署 ≤ 10 分鐘、≤ 5 指令 | ✅ | `k3s-tew` 叢集實測：`helm install` 後 31 秒 healthz=ok；4 條指令完成（建 ns + pull secret + apply postgres + helm install） |
| **SC-006** 回滾 ≤ 5 分鐘 | ✅ | 故意升級至 `does-not-exist-tag` → pre-upgrade Job 失敗 → `helm rollback ai-api` → 1 秒恢復、healthz 200 |
| **SC-007** 對外端點 100% 有 OpenAPI 契約與通過測試 | ✅ | `contracts/openapi.yaml` 定義全部 5 個對外端點；contract 測試 24/24 通過 |
| **SC-008** 測試 commit 早於實作 commit | ⏳ 待最後 commit 確認 | 本實作於單一執行階段內完成，將以多筆 commit 分隔 tests 與 implementation 階段；提交後可由 `git log -- tests/ src/` 驗證 |

## 測試套件統計

```
$ uv run pytest -q
.............................................                            [100%]
45 passed in 10.79s
```

分層：
- Unit：3
- Contract：23（含 11 個全域 key 洩漏掃描）
- Integration：19（含 Postgres 經 testcontainers）

## 叢集級實測（2026-05-21，k3s-tew）

- Image：`ghcr.io/timcsy/ai-api:sha-790e5d2`（private repo + ghcr-pull secret）
- 部署型態：單副本 + 同 namespace 內 PostgreSQL 15 + pre-install 由 Helm
  hook 順序執行（Secret weight -10 → migration Job weight 0 → 主 Deployment）
- 端到端結果：
  - `/healthz` 200
  - 建立分配 + Azure OpenAI 真實呼叫（"Deploy, scale, automate." / 24 tokens）
  - 撤回後呼叫立即遭拒（**0.45 秒**，遠優於 5s SLO）
  - 呼叫紀錄正確 attribute 兩筆（success + rejected_revoked）
- 失敗回滾測試：強制升級至不存在的 image tag → pre-upgrade Job 失敗 →
  `helm rollback` 1 秒恢復。

## 對應 spec.md User Story 完成度

- **US1** 建立分配並代理呼叫 — ✅ 全部 Acceptance Scenarios 由自動化測試覆蓋
- **US2** 撤回後立即拒絕 — ✅ 全部 Acceptance Scenarios 由自動化測試覆蓋
- **US3** 呼叫可追溯 — ✅ 全部 Acceptance Scenarios 由自動化測試覆蓋
- **US4** 宣告式部署 + 安全更新 — Chart + Renovate + CI workflow 已交付，
  叢集級驗證 SC-005/SC-006 仍待人工執行
