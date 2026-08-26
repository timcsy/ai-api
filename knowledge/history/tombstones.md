# 墓碑目錄（考慮過、否決/延後，從未生效）

> 這是**目錄**、不是 transition（沒有東西被 superseded）。每條記：考慮過什麼、為什麼不選（最濃的 why）、
> thaw（解凍）條件。與 `history/NNN-*.md`（曾生效→被改）分開。

## 治理 / 配額

- **每日上限（Daily Cap）**：2026-06-03 曾列候選（源於外部回饋的延伸推導、非核心需求）→ **否決**；
  「月配額 + 異常偵測自動隔離 + 暫停」已足夠覆蓋「單一使用者吃光共享配額」。連帶移除階段 13 預埋的
  `allocation_daily_cap_exceeded` event type 與 email 範本。階段 33 成本制配額刻意**不重做它**（USD 月度
  統一治理，非每日 per-unit 粒度——兩者不同軸）。**thaw**：若真需要日粒度硬上限再重建。
- **配額池按 model/Team/部門切多池**：否決（首版單一全域池）。**thaw**：多租戶/部門獨立預算出現時。
- **跨月借貸 / token roll-over / EWMA 時間平滑**：否決（首版單月窗）。**thaw**：觀察數月後若公平性需要。

## 上游 / 架構

- **整包改用 LiteLLM Proxy form**：**否決**；判準是「領域第一公民同不同軸」（litellm 是 key/user/team、
  我們是「分配」）而非功能重疊度（build-vs-adopt）。realtime 也因此 build 薄 relay（音訊不能繞過 gateway，
  否則失去歸戶 + 即時撤回）。**thaw**：若平台核心抽象改為與 litellm 同軸（幾乎不會）。
- **LiteLLM virtual keys 直接當對外憑證**：否決（撤回 SLO/審計受限於 litellm schema、配置變更需 reload）。
- **直呼 Azure OpenAI SDK（棄多 provider 抽象）**：否決（違反可替換性、難擴充多供應商）。
- **JWT + 短 TTL / 進程內快取 + pub/sub 做撤回**：否決（會「等 token 過期」違反即時撤回 / 複雜度違 YAGNI）。
- **Redis 為主儲存 / MongoDB**：否決（撤回快但缺審計耐久性 / 事務與審計查詢弱）。
- **LiteLLM `mode → responses` 衍生**：⚰️ 移除（概念混淆 + 會被同步洗掉的 latent bug；見 `007-*`）。
- **硬編價格「常見範本」**：⚰️ 退役（改用 LiteLLM 建議價，帶入＝同步同一機制；階段 24）。

## 端點

- **video_generation**：非同步 job（送出回 job id、要 poll、用量等 job 完成才算），破壞「同步一請求一回應
  一筆帳」假設 → **獨立子專案、不綁進來**。**thaw**：有 job 狀態子系統時。
- **vector_store**：有狀態、跨多次呼叫，不符「per-call 計量歸戶」的 gateway 模型 → **傾向誠實不做**（未定案）。
- **whisper / STT per-second（按時長）計費**：**延後**（非否決）——`litellm.TranscriptionResponse` 無
  `duration` 欄、算秒數需第三方音訊庫（違「不新增套件」）；diarize/transcribe 有 token 已足夠。**thaw**：
  取得音訊長度來源 / 願加音訊庫時。
- **image_edit / search 真分支實測**：**延後**——Azure 不提供，待接非 Azure provider（FLUX/Stability /
  Perplexity/Tavily）才能真打驗證（架構已就緒、recipe 待補真分支）。

## 測試 / 流程

- **3b.7 Playwright E2E**：**descope**（2026-06-03）——solo 維運、回歸防線實為 contract/unit + lint/typecheck/
  build + 部署後手動煙霧；notification 上線暴露的兩個真 bug（NetworkPolicy egress、密碼留白）Playwright 在 CI
  都抓不到（前者需真 cluster、後者該由 contract test 守）。**thaw**：有他人 contribute、不再單一驗證者時。
- **第二掃描器（OSV / Grype）進 CI**：否決 → 改「季度手動」第二意見。**thaw**：CI 預算允許時。
- **cosign 簽章 + admission control / 自架 trivy-server / external-secrets+Vault / FQDN-aware egress**：
  階段 2.5/2.6 明確排除，留後階段（皆需額外基建）。
- **獨立 Tag entity**：否決（tag 只是字串集合、無 metadata → 讓 join table 自當 source of truth）。**thaw**：
  tag 需要 color/description 等 metadata 時（純 schema 增量）。
- **Codex 桌面版行程自動偵測**：可選加分、**未做（YAGNI）**——偵測不到不代表沒裝，提醒為主。**thaw**：誤裝率高時。
- **重構身分模型（群組/方案）**：被維護者打斷（階段 44）——使用者的痛是「一次撈全部一個個點」，通用解 = 篩選
  × 全選 × 批次，不是概念重構。**thaw**：真出現群組/方案級的授權需求時。
