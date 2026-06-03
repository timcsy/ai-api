# Phase 0：研究與技術抉擇

本檔記錄實作前的技術選擇與比對。每個議題的格式：**Decision / Rationale / Alternatives**。

---

## R1：SMTP client library

**Decision**：採用 `aiosmtplib` 作為新依賴

**Rationale**：
- 本平台核心是 FastAPI async 架構；用同步 `smtplib` + `asyncio.to_thread` 會在事件 hook
  路徑引入 thread context switch，行為較難 reason about
- `aiosmtplib` 是 pure-async，無 native dep（除 `cryptography` 既已存在），輕量
- API 穩定（>= 2.0 系列）、與 stdlib `email.message.EmailMessage` 完全相容
- 既有 lesson「採用前先驗證 SDK 的能力邊界」（experience.md）— 已驗證 `aiosmtplib.send()`
  支援 STARTTLS、TLS、authentication、custom timeout、明確 exception 型別

**Alternatives considered**：
- **stdlib `smtplib` + `asyncio.to_thread`**：零新依賴；但 sync API 包 async 是 anti-pattern，
  log/trace 上下文易斷掉
- **`emails` 套件**：高階 wrapper，但又疊一層抽象，違反 YAGNI；且非 async-first

---

## R2：密碼加密儲存

**Decision**：沿用既有 `PROVIDER_KEY_ENC_KEY`（Fernet）

**Rationale**：
- 既有 `ProviderCredential` 已用此 pattern；無新基礎建設、無新 Helm value、無新 K8s Secret
- experience.md 既有教訓「對稱加密金鑰要在 pod 啟動時就驗證」已套用於同一把 key——pod
  啟動時若 key 缺失即 fail-fast，本功能自動受益
- 解密失敗時對應 FR-026「憑證需要重新輸入」狀態：在 `NotificationConfigService.get()`
  catch `InvalidToken` 並回 `credentials_invalid` 狀態給上層

**Alternatives considered**：
- **新增獨立 `SMTP_PASSWORD_KEY`**：違反 YAGNI；多一個金鑰要管、要驗、要文件化
- **不加密、存明文**：違反 FR-003；亦違反 principle「憑證隔離」精神
- **委外 KMS（如 AWS KMS）**：過度工程；本平台無外部 KMS 整合

---

## R3：去重模型——立即寄 vs. 延遲聚合

**Decision**：**立即寄第一筆 + DB 紀錄作為 5 分鐘 suppression gate**；不送 follow-up
summary email；後續同型別事件僅落 `notification_record` 標 `outcome=suppressed`

**Rationale**：
- 同時滿足 FR-017（30s SLO）與 FR-018（每 5 min 每型別 ≤1 封）
- 「延遲 5 min 聚合再寄」會違反 FR-017
- 「立即寄 + 5 min 後再寄 summary」會違反 FR-018（變成 2 封）
- 既有 admin UI 已有 `notification_record` 歷史列表，可顯示「N 筆已合併入此窗」
  → FR-019 的「count」改為**在歷史 UI 呈現**，不在 email body；spec 因此會在
  notes 補充微調
- multi-replica 環境每窗每型別至多 N 封（N = replica 數量，目前 2）。實務上同類事件
  不會在毫秒內同時被多 replica 觸發（anomaly detector 是 cronjob 單 instance；
  其他 event 由 audit emit 點同步觸發 hook，每筆事件只走一個 replica）→ 多 replica
  重複機率近乎 0；不做 distributed lock

**實作流程（每筆事件）**：
1. `audit.record()` 寫 audit event（既有）
2. 若 event_type 在 v1 通知清單中 → 觸發 `notifier.notify(event)` as `asyncio.create_task`（fire-and-forget）
3. notifier 內：
   - 查 `NotificationConfig`，無/disabled → 落 `notification_record(outcome=skipped_disabled)`、return
   - 查 `notification_dedup_bucket` 中 `(event_type, window_start ≤ now < window_end)` 是否存在
     - 存在 → 落 `notification_record(outcome=suppressed)`、bucket count +1、return
     - 不存在 → 新建 bucket（`window_start=now, window_end=now+5min`）、寄信、落
       `notification_record(outcome=sent or send_failed_*)`

**Alternatives considered**：
- **延遲 5 min 聚合再寄**：違反 FR-017
- **APScheduler 排程 follow-up summary**：違反 YAGNI；新增背景排程器與其狀態管理
- **in-memory dedup（per-replica dict）**：multi-replica 各自獨立 → 上限 N 封反而比 DB 共享更糟；
  restart 全失

---

## R4：背景排程器

**Decision**：**不引入新排程器**；歷史 GC 用既有 helm cronjob pattern（複製 `storedResponseCleanup`）

**Rationale**：
- R3 採立即寄送 + DB gate，無 deferred dispatch 需求 → 不需要 APScheduler / Celery
- 30 天保留歷史的 GC 是低頻單純查刪，沿用既有 `stored_responses_cleanup` cronjob 即可
- 既有 `anomaly` 也是 helm cronjob → 模式一致

**Alternatives considered**：
- **APScheduler in-process**：用於 R3 的 delayed summary——但 R3 不需要
- **Celery + Redis**：嚴重過度工程；無其他用 case

---

## R5：事件 → notifier 訂閱機制

**Decision**：**直接在 `audit.record()` 內加 hook**——若 event_type ∈ v1 訂閱清單，
觸發 `asyncio.create_task(notifier.notify(event))`

**Rationale**：
- 最低延遲、最少元件
- audit emit 是現有單一通過點，所有候選事件都會經過——無漏網
- `create_task` 為 fire-and-forget；notifier 內 try/except 不向上傳遞失敗 → FR-025 滿足
  （寄信失敗不影響 audit 寫入）
- experience.md「proxy relay ≠ proxy observability」原則應用：notifier 是本地觀測層，
  獨立於 audit 主流程之外

**Alternatives considered**：
- **背景 poller 查 audit_events**：延遲不可控；輪詢 overhead
- **DB trigger / LISTEN/NOTIFY**：耦合 PostgreSQL（破壞 SQLite dev 環境）；複雜度爆
- **訊息佇列（Redis Streams / Kafka）**：過度工程；無其他 case

**訂閱清單（v1 寫死於 code，operator 可 Helm value override）**：
- `allocation_quarantined`（FR-009）
- `responses_upstream_error_burst`（FR-010）— **新 audit event type**；
  既有 `upstream_error` 個別事件由新 detector 在 sliding 5-min 窗 ≥10 次時觸發
- `provider_credential_auth_failed`（FR-011）— **新 audit event type**；
  從 proxy 層偵測 401/403 from upstream 時觸發
- `allocation_daily_cap_exceeded`（FR-012）— Phase 16 上線後才會觸發；現階段為 no-op

---

## R6：Email 內容與格式

**Decision**：以 Python f-string 組裝；subject 純文字 ≤50 字；body 純文字含一條
HTML link（client 不渲染 HTML 仍可讀；連結被當作文字呈現）；無 Jinja2

**Rationale**：
- 4 種事件型別、結構簡單；f-string 與 module-level constant template 足夠
- Jinja2 為新依賴；違反 YAGNI（既有專案無 template engine）
- 純文字 + HTML link 是「最低渲染複雜度，最高 client 相容性」的 standard pattern

**範本（research note；最終於 `services/notifier.py` 落 code）**：

```text
Subject: [AI API] 分配自動隔離 — alloc abc12345

Body:
管理員您好，

一筆分配剛剛被異常偵測器自動隔離。

  - 分配：abc12345（小明的 GPT-4o 憑證）
  - 觸發原因：過去 1 小時 1100 calls，baseline 100/hr，11× 突增
  - 時間：2026-06-02 03:14 (UTC+8)

請至以下頁面確認狀況並決定是否解除：
https://ai-ccsh.tew.tw/admin/observability/allocations

— AI API Manager
```

**Alternatives considered**：
- **Jinja2 + HTML rich email**：過度；UI 簡潔即可
- **MJML / responsive HTML**：完全 overkill 對「給 admin 看訊息」

---

## R7：重試政策

**Decision**：**v1 不重試**；失敗即落 `notification_record(outcome=send_failed_*)`，
admin 可在 UI 看到並選擇是否手動 re-test（修正設定）

**Rationale**：
- YAGNI：v1 無重試的證據壓力
- 既有 SMTP 服務（Gmail SMTP、Workspace SMTP）穩定度高；transient 失敗罕見
- 真實 transient 失敗會被「下一個事件」觸發重新嘗試
- 加重試需要：失敗佇列、退避策略、上限、佇列持久化——複雜度大幅上升
- experience.md「拒絕路徑必須在 raise 前綁定上下文」應用：失敗時 log 完整資訊
  （event_id / recipient / SMTP server response code / error class）

**Alternatives considered**：
- **指數退避重試 3 次**：v1 不需要；之後若實測發現 transient 比例高再加
- **dead-letter queue**：嚴重 overkill

---

## R8：去重識別欄位（window keying）

**Decision**：以 `event_type` 單獨作為 key；window 為「該 event_type 最早一次該窗的時刻
+ 5 分鐘」

**Rationale**：
- spec FR-018 明寫「same-event-type」
- 不以 `(event_type, recipient_set)` 為複合 key——目前單一全域 recipient 清單，無需區分
- window 從第一筆事件開始算（而非固定整數分鐘邊界），符合「事件爆發從第一筆開始算窗」直覺

**Alternatives considered**：
- **固定整點 5-min bucket**（00:00, 00:05, ...）：實作略簡，但容易在 bucket 交界處剛好同型別兩封信
- **以 minute-level cron 對齊**：違反 R4「不引入排程器」原則

---

## R9：通知歷史保留與清理

**Decision**：30 天保留；每日凌晨 03:30 UTC helm cronjob 跑 `DELETE FROM notification_record
WHERE created_at < now() - interval '30 days'`；複用 `storedResponseCleanup` 模式

**Rationale**：
- FR-024 規定 ≥30 天
- helm cronjob pattern 已存（stored_responses、anomaly），複製成本低
- 不影響在用資料：bucket 不在歷史內，bucket 在 window 過期後即可刪（同一 cron 順手清）

**Alternatives considered**：
- **無限保留**：DB 膨脹；v1 不需要
- **應用層 retention policy**：增加 boot-time job；違反 YAGNI

---

## R10：通知設定的單例性質

**Decision**：`notification_config` 表 enforce 全表至多一列（DB constraint：
`CHECK (id = 1)`，single-row pattern）

**Rationale**：
- spec key entities「每個平台部署一份」明寫
- 比「無 unique 約束 + 應用層強制」清楚、防誤改
- pattern 在 K8s 環境常見（如 `kube-system` 的 Singleton ConfigMap）

**Alternatives considered**：
- **每 admin 一份**：FR 假設明白排除（v1 共用設定）
- **無 DB 約束，僅 service 層守**：易於繞過、增 bug 面

---

## R11：admin UI 主題與既有風格

**Decision**：沿用既有 shadcn/ui + 既有 admin sub-nav；新頁 `/admin/notifications`
加入 ADMIN_SUBNAV，icon 用 `lucide-react` 的 `Bell`

**Rationale**：
- experience.md「同一概念的 UI 做兩份一定會 drift」應用：歷史 list、設定 form、test
  button 均沿用既有 admin 表單 pattern（如 `/admin/access`、`/admin/providers`）
- 不引入新 design system
- `Bell` icon 為未來 web push notification badge 預留位置（Phase 13 後續）

**Alternatives considered**：
- **獨立 modal 取代頁面**：設定資訊與歷史 list 同頁更直覺；modal 顯示密度低
- **設定 + 歷史分兩頁**：違反「最容易安裝」設計目標

---

## R12：SMTP 連線 timeout 與安全性

**Decision**：
- connect timeout：15 秒
- send timeout：30 秒（與 FR-017 對齊）
- TLS：優先 STARTTLS（port 587）；admin 可填 port 465 直接 TLS；不允許 plaintext port 25
- TLS verify：預設 verify=True（沿用 `cryptography` 既有 CA bundle）

**Rationale**：
- Gmail SMTP / Workspace SMTP 兩家都支援 STARTTLS:587 與 TLS:465
- experience.md「對稱加密金鑰要在 pod 啟動時就驗證」精神：寄信前先驗 TLS 握手，握手失敗
  立即 surface 錯誤
- 拒絕 port 25 plaintext 是 modern best practice；如真有 legacy 內網 SMTP 後續可考慮 opt-in

**Alternatives considered**：
- **允許 plaintext port 25**：違反 modern email transit 安全慣例；學校 SMTP 多半要求 TLS
- **強制 TLS 不允 STARTTLS**：限制過嚴；Workspace SMTP 主要走 STARTTLS

---

## R13：rate / overload 防護

**Decision**：**v1 不另外加 rate limiter**；既有去重機制（R3）已將寄信頻率上限為「每事件型別 ≤ 12 封/小時」（5 min 窗 → 12 窗/小時）；Gmail SMTP 500 封/天上限充裕

**Rationale**：
- 4 種事件型別 × 12 窗/小時 = 48 封/小時 = 1152 封/天（理論上限）
- 但實務上同型別連續觸發 5 分鐘以上不暫停的情況極罕見（要嘛事件停了、要嘛 admin 介入了）
- 預期日常 5 封/天/部署、爆發 100 封/天/部署，遠低於 500/天上限

**Alternatives considered**：
- **token bucket rate limiter**：YAGNI；既有去重已足
- **per-recipient daily cap**：v1 不需要

---

## 研究結論

所有 NEEDS CLARIFICATION 與技術未知已收斂。可進入 Phase 1。
