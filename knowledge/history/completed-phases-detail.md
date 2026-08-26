# 已完成階段索引（階段 1–44）

> 本檔是階段索引（spec 編號 / migration / 交付重點 / 對應弧與轉移）。`vision.md`〈路線圖〉只留標題 +
> 完成標記 + 一句交付；因果轉移見 `history/NNN-*.md`；否決選項見 `tombstones.md`；早期工具坑見
> `lessons-archive.md`。**rev 數字提醒**：階段 1–39 敘述的 rev 是當時 tew 計數、2026-08-07 tew 退役後失效
> （見 `014-*`）；往後只認 ccsh 計數（截至 `9ec5eea` = ccsh rev 25）。

## 對照表

| 階段 | spec | migration | 交付重點 | 完成日 | 相關 history |
|---|---|---|---|---|---|
| 1 | 001 | 0001+ | 分流核心：gateway 代理 Azure、可撤回憑證、每次查 DB 現況 + server-side session | 2026-05-21 | 001 |
| 2 | 002 | | 認證抽象（Google OIDC + local password）、成員/分配 admin API | 2026-05-22 | 005 |
| 2.5 | 003 | | provider allowlist（空即 fail-fast）、NetworkPolicy、Trivy、per-alloc quota+異常、distroless | 2026-05-22 | |
| 2.6 | 005 | | workflow SHA pin、排程重掃開 issue、SBOM、lockfile fail-fast | 2026-05-22 | |
| 3a | 004 | PriceList/CallRecord | 多維用量、月配額、point-in-time 計費、CSV/JSON | 2026-05-22 | |
| 3b | 008/009/010 | 0011 | 前端 stack + member view + admin suite（5 視圖合併 PR、is_admin 雙軌） | 2026-05-24 | 002 |
| 3c | 006 | RebalanceLog | 自適應配額池（Σq=T、保底、quota_locked、service 豁免） | 2026-05-22 | |
| 4 | 007 | model_catalog | 模型為第一公民目錄 + facet filter；YAML upsert 永不刪 | 2026-05-23 | |
| 5 | 012 | provider_credentials/member_tags | 4 provider、Fernet 憑證、tag 存取、可見性=gate∩policy | 2026-05-25 | 001 |
| 5.1 | 013 | | admin sub-nav 11→6（journey-oriented） | 2026-05-25 | 002 |
| 5.2 | 014 | tag_rules/0012 | first-match-wins 自動 tag（regex 防 ReDoS） | 2026-05-26 | |
| 6 | 015 | self_service_reclaim_locks | 自助領取憑證 + 撤回鎖定 | 2026-05-26 | |
| 7 | 016 | (無) | 價目 admin UI（append-only）；落地即從觀測搬 Model 區 | 2026-05-27 | 003 |
| 8 | 017 | | create_admin CLI（helm hook）+ 啟動防呆；bootstrap token 退 break-glass | 2026-05-27 | 004 |
| 9 | 018 | (無) | `/me/usage`（本人隔離 + has_unpriced） | 2026-05-28 | |
| 10 | 020 | (無) | 成員端 polish；呼叫端點單一來源；admin 暫停/恢復憑證（019） | 2026-05-28 | |
| 11 | 021 | 0013 | `/v1/responses` 全鏈（統一 litellm、SSE、reasoning/cached 計費、store/TTL） | 2026-05-29 | |
| 12 | | | 白名單退 bootstrap-only；anomaly 對 service 豁免；quarantine 可視；公開化 MIT | 2026-05-30 | 005 |
| 13 | 022 | notification_config/0014 | admin 自助 SMTP + 去重寄信（首個 env→DB 單例） | 2026-06-03 | |
| 14 | 024 | (無) | 導入 recharts（單一色盤）；首頁最多 3 圖 | 2026-06-03 | |
| 15 | 023 | (無) | tag rollup（group_by=tag、刻意重疊、admin-only） | 2026-06-03 | |
| 16 | 025 | (無) | 手機 RWD（`.responsive-table`、Sheet；零新依賴） | 2026-06-03 | |
| 17 | 026 | (無) | 成員端用量圖表（範圍取自 session） | 2026-06-04 | |
| 18 | 028 | 0015 | 每分配多 per-device 憑證（Credential 1:N、裝置名 + last_used_at） | 2026-06-04 | 006 |
| 19 | 029 | device_authorizations/0016 | 一鍵裝 Codex + device-flow（RFC 8628 精神、三平台真機） | 2026-06-08 | |
| 20 | 030 | 0017 | scoped application credential（credential↔allocation M:N）；既有 token 零回歸 | 2026-06-05 | 006 |
| 21 | 031 | (無) | 統一「應用金鑰」、單一管理處、可改名；金鑰區降唯讀顯連坐 | 2026-06-05 | |
| 22 | 032 | (無) | 會員介面分頁化 + 金鑰/分配白話解釋 | 2026-06-05 | |
| 23 | 033 | 0018 | 目錄↔LiteLLM（建議來源 + 來源標記快照）；PriceList 仍是計費真理 | 2026-06-08 | |
| 24 | 034 | (無) | 模型編輯單一中樞、退役硬編價格範本 | 2026-06-08 | 002 |
| 25 | 035 | (無) | responses 三軸解耦、實測+手動雙來源、runtime 軟化閘門 | 2026-06-08 | 007 |
| 26 | 036 | (無) | 依 model_kind 測模型；會計費種類確認才打；只寫 audit | 2026-06-08 | 008 |
| 27 | 037 | (無) | 應用分頁（Codex 第一個應用） | 2026-06-09 | |
| 28 | | (無) | 應用商店化（tile + 詳情 + 推薦） | 2026-06-09 | |
| 29 | 038/040/041 | 0019 | 多端點開放 + 計費一般化（NULL⇒token 零回歸） | 2026-06-11 | |
| 30 | 039 | (無) | 成員安全刪除（ORM 顯式連帶、孤兒保留）+ 批次 | 2026-06-10 | |
| 31 | 042 | (無) | 資料驅動端點 registry（engine/spec/registry）+ moderation/search/image_edit | 2026-06-11 | 009 |
| 32 | 043 | (無) | `/v1/realtime` 直連 WS 薄 relay（不經 litellm）；按秒計費 | 2026-06-12 | |
| 33 | 046 | 0020 | 成本制配額（USD 月上限、不進池、取較嚴） | 2026-06-13 | |
| 34 | 049 | (無) | 「如何呼叫」可發現性（金鑰入口、應用總站、單一共用元件） | 2026-06-27 | |
| 35 | — | | 供應鏈 starlette/FastAPI major bump（**規劃中**，暫掛 2 CVE） | — | |
| 36 | 050 | (無) | `GET /v1/models`（依金鑰 scope）+ Copilot 卡真機 | 2026-06-28 | |
| 37 | 051 | (無) | 會員 IA 重排（純重排、單一 MAIN_NAV） | 2026-06-28 | |
| 38 | 052 | (無) | Codex 安裝硬化（codex logout + 整檔覆寫 + 備份 + 桌面版提醒） | 2026-06-29 | |
| 39 | 053 | pool_config/0021 | 配額池 T/保底移前端（DB 單例 + 建議值） | 2026-06-29 | 011 |
| 40 | 054 | anomaly_config/0022 | 異常偵測 v2（稀疏 baseline 退絕對 + admin 可暫停） | 2026-07-02 | 012 |
| 41 | 055 | (零) | 本地登入允許帳號（重用 email 欄） | 2026-07-02 | 013 |
| 42 | 056 | (零) | 逐筆記錄（cost_usd/quantity/unit + admin records + PerCallScatter） | 2026-07-03 | |
| 43 | 057 | 0024/0025 | 第一方 OAuth（Auth Code + PKCE）；redirect 白名單 admin 可編 | 2026-08-25 | 015 |
| 44 | (無 spec) | (無) | 帳號管理批次 + 篩選（成員 + 分配） | 2026-08-25 | |

## 階段 44 後的無 spec 維護（Arc 8，2026-08 為主）

上線後真機/真上游/真 cluster 暴露的一批修復（本機/CI 全綠）——各自的 why 已蒸餾進 `experience.md`：
OCR 圖片 passthrough（選填參數白名單）、chat/completions 串流（收到 usage 當下記帳）、推理模型 temperature
drop + diarization chunking_strategy inject（反應式參數協商）、multipart UploadFile（starlette vs fastapi
isinstance）、nginx generic `/v1` timeout（catch-all location）、BigInteger 溢位、shell `${VAR}` locale、
Dockerfile frozen-deps 慢拉治本（見 `016-*`）、last_used_at 短交易（見 `010-*`）、tew→ccsh 遷移（見 `014-*`）。

## 事故

- **2026-06-29 高併發塞車**（ccsh 遷入後）：last_used_at 熱列鎖跨慢呼叫 → 連線池打爆。治本見 `010-*`。
- **2026-08-06 GitHub Actions runner outage**：本機 buildx 直推 ghcr 逃生路（tag 沿用 `sha-<git短碼>`）。
