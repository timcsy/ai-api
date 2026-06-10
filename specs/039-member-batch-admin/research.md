# Research: 管理員成員管理批次化 + 安全刪除

## R1：連帶刪除——服務層 ORM 顯式處理，不靠 DB 端 ondelete cascade

- **Decision**：安全刪除在 `MemberService` 內以 ORM 顯式執行整條連帶，**不依賴資料庫 FK 的 `ondelete` 行為**。順序：
  1. 撤回該成員所有 active 分配（沿用 `AllocationService.revoke` 的狀態機 + 即時撤回語意，並寫稽核）。
  2. 把該成員所有分配的 `CallRecord.allocation_id` 設為 `NULL`（保留呼叫史；`subject` 已存 email，歸屬不失）。
  3. 刪除該成員的 `credential_allocations`（連結）、`credentials`、`allocations` rows。
  4. 刪除 `member`。
  5. 全部在**單一交易**內 commit；任一步失敗則整筆 rollback（單筆原子，FR-003）。
- **Rationale**：`src/ai_api/db.py` **未設定 `PRAGMA foreign_keys=ON`**，故 SQLite（dev/CI）**不強制** FK 的 `ondelete`（SET NULL / CASCADE / RESTRICT）；Postgres（生產）卻會強制。若靠 DB cascade，測試（SQLite）跑得過、生產（Postgres）行為不同——正中經驗教訓「dev/prod 用不同 DB 後端時『能跑』≠『正確』」。顯式 ORM 處理**可攜、可測、可見**，且能在每步插入稽核與即時撤回語意。
- **Alternatives considered**：
  - *靠 DB ondelete（CallRecord SET NULL、credential CASCADE）*：schema 已具備，但 SQLite 不強制 → 測試無法真實驗證、dev/prod drift。否決。
  - *在測試開 `PRAGMA foreign_keys=ON`*：讓 SQLite 也強制，但 (a) 仍把刪除語意藏在 DB 層、稽核/撤回不易插入；(b) 改動 DB 連線設定影響全專案、超出本功能範圍。否決。

## R2：批次交易邊界——逐筆獨立 tx，不整批回滾

- **Decision**：批次刪除與批次新建**逐筆獨立處理、各自獨立成敗**：單筆失敗只記入該筆結果，不影響、不回滾其他筆（FR-007、FR-012）。回傳逐筆結果陣列（成功/失敗 + 原因碼）。實作上每筆用**獨立交易邊界**（單筆刪除內部仍為一個原子 tx，見 R1）。
- **Rationale**：批次是 admin 對「一堆獨立對象」的操作，使用者期望「能刪的都刪掉、刪不掉的告訴我哪些」，而非「一筆壞全部不動」。呼應經驗「拒絕路徑必須在 raise 前綁定 context」——每筆失敗需綁定該成員 id + 原因。
- **Alternatives considered**：
  - *整批單一交易、一筆失敗全回滾*：對 admin 清理情境體驗差（一個壞帳號擋住整批），且與「逐筆摘要」的需求矛盾。否決。
  - *平行處理（asyncio.gather）*：admin 低頻操作，數百筆順序處理即可；平行徒增交易/連線競態複雜度，違反 YAGNI。否決。

## R3：防呆守衛——不可刪自己、不可刪最後一位 active 管理員

- **Decision**：在服務層（單筆安全刪除的入口）加兩道守衛，單筆與批次共用：
  1. `target_member_id == current_admin_id` → 拒絕（`cannot_delete_self`）。
  2. 若 target 是 active 管理員，且刪除後系統 active 管理員數會歸零 → 拒絕（`last_admin`）。
  守衛在連帶刪除**之前**檢查；批次中觸發守衛的單筆記為失敗、不影響其他筆。
- **Rationale**：FR-014/FR-015 + 經驗「可登入的首位管理員是部署的一部分」的反面——別讓 admin 把自己鎖在門外。放服務層（非僅端點）確保單筆/批次/未來任何入口都受保護（集中管理、原則 5）。
- **Alternatives considered**：只在前端擋——不可靠（API 可直接打），否決。只擋「自己」不擋「最後一位 admin」——別人可刪掉唯一剩的 admin，否決。

## R4：批次新建的 email 解析、驗證與去重

- **Decision**：接受多行文字（每行一個 email），後端：trim 空白、忽略空行、**同批內去重**（重複行記為 `duplicate`）、用既有 email 正規化/驗證（沿用 `MemberService.create` 既有的 normalize + 驗證路徑）。逐筆套既有 `create(provider=local_password, send_invitation=True)`，回每筆 `{email, status, invitation_url?}`，status ∈ {created, exists, invalid, duplicate}。
- **Rationale**：沿用既有單筆 `create` 的驗證與邀請連結產生（`invitation_plaintext` → URL），不另寫驗證規則（原則 7：批次＝單筆迴圈）。已存在 → 既有 `MemberAlreadyExists` 對映 `exists`。
- **Alternatives considered**：CSV 檔上傳——spec 已 descope（貼文字清單為主），YAGNI。前端先驗證 email——可加即時提示，但**權威驗證在後端**（前端僅輔助）。

## R5：前端沿用既有批次多選 UI 樣板

- **Decision**：成員列表 `admin/members.tsx` 沿用 `admin/tags.tsx` 既有模式：`selected: Set<string>` 選取狀態、表頭/列 checkbox、選取後顯示批次動作列（「已選 N 位」+「批次刪除」）。批次新建用既有 `Dialog` 樣板（多行 textarea + 提交 + 結果摘要列表）。單筆刪除確認對話框升級為顯示連帶影響（分配數/憑證數、金鑰立即失效、用量保留）。
- **Rationale**：經驗「同一概念的 UI 做兩份一定會 drift → 抽共用元件」。若多選邏輯之後第三處要用，再抽 `useRowSelection` hook（目前 tags + members 兩處，尚在「三段可保留」範圍，YAGNI）。
- **Alternatives considered**：立刻抽共用 selection hook——目前僅兩處，依憲章 V「三段相似可保留」暫不抽。

## R6：零 migration / 零新 enum 確認

- **Decision**：本功能**不新增表、不新增欄位、不新增 migration、不新增 enum**。`alembic heads` 維持 `0018_model_litellm_sync`。
- **Rationale**：所有連帶以既有 schema + ORM 顯式刪除達成；audit `AuditEventType.member_created`/`member_deleted` 皆已存在；批次結果為端點回傳形狀（非持久化）。
- **驗證**：`grep` 確認 `member_created`/`member_deleted` 已在 `models/auth_audit.py`；`alembic heads` = 0018（單一 head）。
