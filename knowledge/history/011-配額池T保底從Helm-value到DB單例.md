# 011：配額池 T/保底從 Helm value 到 DB 單例（admin 可編）
> 日期：2026-06-29

## 轉移
- 舊（superseded）：自適應配額池的總額 T 與每分配保底是 Helm/env 的 infra 設定，要調得工程師改 value 重部署；
  admin 也無從得知「該設多少」。
- 新（spec 053 / 階段 39，migration 0021）：`pool_config`（`CHECK id=1` 單例）**從 env lazy-seed**、之後 DB 為
  單一真理；admin 在配額池監控頁可編輯 + 依近月用量算的**建議值**（建議 T ≈ 近月用量 × 2）。

## 為什麼變
T/保底本質是**業務/治理決策（配額），不是 infra 參數**——依「可見性 vs 可編輯性」判準（改錯爆炸半徑 × 改動
頻率），業務治理類該可編、不該停在唯讀顯示；違反可達性（admin 該能自助、不必靠工程師改 value 重部署）。
落地守 env→DB 單例模式：首讀 lazy-seed 保「搬家當下零行為變更」、env 退為 bootstrap、**所有讀取點**
（`apply_rebalance` + 監控頁 GET）都改讀單一入口。

## 狀態
✅ 已採用。這是 env→DB 單例模式的第二次套用（首例 `notification_config` 階段 13）。
生效於下次再分配、非即時改寫；不改再分配演算法本身。
