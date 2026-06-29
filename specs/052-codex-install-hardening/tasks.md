---
description: "Task list for Codex 安裝腳本硬化"
---

# Tasks: Codex 安裝腳本硬化——既有登入/設定殘留處理 + 桌面版關閉提醒

**Input**: Design documents from `/specs/052-codex-install-hardening/`
**Prerequisites**: spec.md、plan.md（皆已產出）。無 data-model/contracts（安裝腳本，非對外 API）。

**Tests**: constitution 強制 TDD。既有 `tests/contract/test_install_endpoint.py` 以**內容存在**斷言為主（base_url / ccsh / login / model / fail-soft）——這些改動後仍在、不破。新行為（logout / 備份 / 桌面版提醒）以**新增斷言**先紅再做。SC-006（三平台真機）為人工驗收、非 CI 可涵蓋。

**檔案協調**：US1/US2/US3 都改同兩個模板（`codex.sh.tmpl`、`codex.ps1.tmpl`）→ 同檔任務**序列**執行。

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 基線：跑 `python -m pytest tests/contract/test_install_endpoint.py -q` 確認起點綠（之後比對零回歸）。

---

## Phase 2: Tests（TDD，先紅；集中於單一 install 測試檔）

- [X] T002 在 `tests/contract/test_install_endpoint.py` 新增斷言（兩個 path 都驗），先紅：
  - **logout 早於 login**：body 含 `codex logout`，且 `codex logout` 的位置在 `codex login --with-api-key` **之前**（`body.index("codex logout") < body.index("codex login")`）。
  - **動檔前先備份**：body 含 `.bak-`（帶時間戳備份）+ 備份相關字樣（如 `備份`）。
  - **桌面版提醒**：body 含 `桌面版`（提醒先關閉）。
  - **既有斷言不改**（base_url / `model_providers.ccsh` / `codex login --with-api-key` / `model = ` / fail-soft `金鑰` / `supports_websockets = false` / 無 `readonly`/`alias codex` 全部保留）。

---

## Phase 3: User Story 1 — 既有登入/設定者一鍵安裝後可用（Priority: P1）🎯 MVP

**Goal**: 殘留登入/設定不再卡住——auth 以 `codex logout`→`login` 重設、config 整檔覆寫成乾淨平台設定。

**Independent Test**: 既有 ChatGPT 登入的機器跑安裝、不清檔 → 可用本平台對話（真機 SC-001）。

- [X] T003 [US1] `src/ai_api/install/codex.sh.tmpl`：① step 2 由 merge 改為**整檔覆寫**乾淨平台 config（`cat > "$CONFIG"` 寫 `model_provider`+`[model_providers.ccsh]` 區塊；移除原 python merge）；② step 4 在 `codex login --with-api-key` **之前**加 `codex logout >/dev/null 2>&1 || true`（清殘留登入、安全 no-op）。step 4 既有 model pin 保留（在乾淨檔上 prepend `model =`）。
- [X] T004 [US1] `src/ai_api/install/codex.ps1.tmpl`：同 T003 的 PowerShell 版（`Set-Content` 寫乾淨 block 取代 regex merge；login 前 `try { codex logout 2>$null | Out-Null } catch {}`）。

**Checkpoint US1**: 兩腳本皆先 logout 再 login、config 為乾淨覆寫。

---

## Phase 4: User Story 2 — 動檔前先備份、可一行還原（Priority: P2）

**Goal**: 改 `config.toml`/`auth.json` 前先帶時間戳備份；備份失敗 fail-loud；完成告知還原方式。

**Independent Test**: 有既有檔的機器跑安裝 → 產生 `*.bak-<ts>` + 輸出還原指引（真機 SC-002）。

- [X] T005 [US2] `codex.sh.tmpl`：在動任何檔前（step 1 前、helpers 後）加備份區塊——`TS=$(date +%Y%m%d-%H%M%S …)`；對 `$CONFIG` 與 `$CODEX_HOME/auth.json` 存在者 `cp` 成 `*.bak-$TS`，**cp 失敗即 `say ERROR + exit 1`**（fail-loud、未改任何檔）；有備份則 say 位置。結尾加一行還原提示。新增 `AUTH="$CODEX_HOME/auth.json"` 變數。
- [X] T006 [US2] `codex.ps1.tmpl`：同 T005 的 PowerShell 版（`$ts = Get-Date -Format yyyyMMdd-HHmmss`；`Copy-Item … -Force`，失敗 `Write-Host ERROR; exit 1`；`$Auth = Join-Path $CodexHome "auth.json"`；結尾還原提示）。

**Checkpoint US2**: 兩腳本動檔前先備份、fail-loud、告知還原。

---

## Phase 5: User Story 3 — 預裝桌面版需先關閉的提醒（Priority: P2）

**Goal**: 卡（主）+ 腳本（輔）提醒先完全關閉 Codex 桌面版（含 Windows 工作列常駐）。

**Independent Test**: 卡與腳本輸出皆出現提醒（真機 SC-004）。

- [X] T007 [US3] `codex.sh.tmpl` + `codex.ps1.tmpl`：在頂部（備份前）加顯眼提醒 echo——「若已安裝 Codex 桌面版，請先完全關閉（含 Windows 工作列／系統匣常駐）再繼續，否則執行中的桌面版可能蓋掉這次設定；裝好再開。」
- [X] T008 [US3] `frontend/src/components/codex-install-card.tsx`：① 在指令區下方加**顯眼 amber 提醒**（兩 OS 皆顯示、強調 Windows 工作列常駐）先關閉桌面版；② **修正過時文案**——`details` 內 CLI 那段「不會重裝、保留你其他設定」已不成立（現為整檔覆寫），改為「會把 `~/.codex` 設定重設為乾淨的平台設定，**你原本的已先備份、可還原**」（呼應「對外文案要與實際行為一致」教訓）。

**Checkpoint US3**: 卡 + 腳本皆有提醒；卡文案與「覆寫+備份」實際行為一致。

---

## Phase 6: Polish & 上線

- [X] T009 跑 `python -m pytest tests/contract/test_install_endpoint.py -q`（新斷言轉綠 + 既有零回歸）+ `ruff check .`；前端 `cd frontend && npx tsc --noEmit && npm run build`（卡改動）。
- [ ] T010 PR + squash-merge（CI 全綠）。**模板是後端檔、卡是前端** → **兩個 image 都 bump**：helm `--reuse-values` + `--set image.tag=sha-<new>` + `--set frontend.image.tag=sha-<new>` + `migrationJob.enabled=false` + storedResponseCleanup。部署後驗 `/install/codex.sh`、`/install/codex.ps1` 200 且含 `codex logout`/`.bak-`/`桌面版`。
- [ ] T011 **SC-006 三平台真機驗收（人工，維護者）**：在「Codex 已用 ChatGPT 登入」的 Windows / macOS / Linux 各跑一鍵安裝——不清檔可用、備份生成可還原、桌面版提醒可見。若 `codex logout` 一步不足/行為有出入 → 回報、據實調整（沿用 Copilot 卡的「部署→真機→修」迴圈）。
- [ ] T012 知識同步（真機過後）：`knowledge/vision.md` 記此階段（Codex 接入硬化）；`knowledge/experience.md` 蒸餾「腳本寫共用設定檔前先備份 + 用工具自身 CLI 重設登入（別硬編格式）+ 長駐 GUI 會搶寫設定要提醒關閉」。

---

## Dependencies & Execution Order

- **T001** → 之前。**T002**（測試先紅）→ 實作之前。
- **同檔序列**：`codex.sh.tmpl` 的 T003→T005→T007 序列（同檔）；`codex.ps1.tmpl` 的 T004→T006→T007 序列（同檔）。T008（卡，獨立檔）可與模板並行。
- **US1（T003/T004）** = MVP（沒它既有登入者就是裝不起來）。US2（備份）、US3（提醒）疊加其上。
- **Polish（T009→T010→T011→T012）**：全綠 → 部署 → 真機 → 知識。

### 平行機會
- `T008`（前端卡）與模板任務（後端）可並行。
- sh 與 ps1 是不同檔，T003∥T004、T005∥T006 可並行（但各自內部序列）。

## Implementation Strategy

- **MVP = US1**：logout + 乾淨覆寫直擊「既有登入裝不起來」。US2 備份是安全網、US3 提醒避坑，一起出貨一次測（維護者偏好「全部一起、部署後真機一次測」）。
- **blind 穩健**：不能先探 Codex → 用「重設到已知乾淨狀態 + 備份可還原 + 用 Codex 自身 CLI」最大化「直接可用」機率；不確定處（logout 是否足夠）交真機驗收迴圈。
- 後端模板 + 前端卡 → 兩 image 一起 bump、一個 PR。
