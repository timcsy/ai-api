# 008：測試模型從 if/elif dispatch 到資料驅動 recipe 表
> 日期：2026-06-11

## 轉移
- 舊（superseded）：階段 26「測試模型」用 `is_supported` 常數 + dispatch `if/elif` 兩處平行維護。
- 新（rev 90, PR #82）：`services/model_test.py` 一張 `RECIPES` 表（kind → 怎麼測 + billable 旗標）當單一真理；
  `is_testable(k) := k in RECIPES`——沒 recipe 的 kind 自動「尚不支援自動測試」、絕不假通過。

## 為什麼變
`is_supported` 說 OCR 支援、dispatch `if/elif` 沒有對應分支 → 靜默 no-op → 假綠「通過 0ms」。「能不能測」與
「怎麼測」兩處平行維護必 drift，失敗模式是最惡的「靜默假成功」。解法：能力查詢**從執行定義衍生**——加種類
沒寫 recipe 就自動誠實回「不支援」。呼應原則 7（資料勝於程式）。

## 狀態
✅ 已採用。`model_kind` 判定優先 litellm `mode`、退 modality（modality 分不出 embedding vs chat）。
測試是真實呼叫但只寫 audit（`model_tested`）、不寫成員 CallRecord（避免無歸屬的影子用量）。
