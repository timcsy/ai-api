# env 設定搬 DB 單例，用 lazy-seed 保「首次零行為變更」

**可判斷主張**：一段設計若是「該可設定、又不想每次 redeploy」的治理/業務設定，且用了「`CHECK id=1`
單例表 + 單一讀取入口（get-or-create）+ 首讀 lazy-seed 自現行 env + env 退為 bootstrap 預設」，就屬這個
概念。若它留了第二個可編輯路徑（env 與 DB 都能改同一值），就是反例（會 drift）。

## 一句話

把治理設定從部署層抬到 admin 自助層，同時守住單一真理——DB 成為 live 唯一真理，env 只在「介面從未設定過」
時當初始預設，搬家當下與現況完全一致。

## 為什麼是它（剪枝力）

- **首次零行為變更**：lazy-seed 讓搬家不改變現狀（不是「上線就套新預設」）。
- **不留平行路徑**：env 退為 bootstrap，避免「顯示值 ≠ 執法值」的沉默 drift（原則 5）。
- **所有讀取點都要改指向單一入口**：不只加端點——既有每個 sink（如 `apply_rebalance`、監控頁 GET）都得改讀
  DB 入口，漏一個就留平行真理。這是套用此模式最容易漏的一步。
- 判準搭配「可見性 vs 可編輯性」：只有**業務/治理**設定（配額、門檻、白名單、通知）適用；infra 設定（body
  size/timeout）該留 Helm、UI 唯讀。

## 本專案的實例（同一模式四次套用）

`notification_config`（階段 13，首例）→ `pool_config`（階段 39，migration 0021）→ `anomaly_config`
（階段 40，migration 0022）→ `oauth_config`（階段 43，redirect 白名單，migration 0024/0025）。

## 投影到三觀點

- **principles**：原則 5（集中管理單一真理）的可複用結構。
- **vision**：〈架構〉的「治理設定」段。
- **history**：`011-配額池T保底從Helm-value到DB單例.md`、`012-異常偵測...v2.md`、`015-OAuth-redirect白名單從env到DB單例.md`。

## 指回

- `concepts/同一件事只能有一條可改寫的路徑.md`
- experience「可見性與可編輯性要分開判」「新增/放寬欄位要追到所有讀取點」。
