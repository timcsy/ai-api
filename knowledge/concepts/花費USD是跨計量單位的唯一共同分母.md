# 花費（USD）是跨計量單位的唯一共同分母

**可判斷主張**：拿一張聚合圖或一條配額規則問「它把不同端點的量加在一起了嗎？加的是 token+頁+張+秒，
還是先各自換算成 USD？」——以 USD 為軸、原生單位只在單一端點明細出現，屬這個概念；把異質單位直接相加，
就是反例。

## 一句話

token / 頁 / 張 / 秒 / 字元彼此**不能相加**；跨端點的聚合、圖表、配額治理一律以「花費（USD）」為共同分母。

## 為什麼是它（剪枝力）

- **計費一般化**：`PriceList`/`CallRecord` 從 token 中心 → 能裝任何單位（migration 0019 純加欄
  `price_unit`/`price_per_unit_usd`/`quantity`/`unit`，皆 nullable、**NULL ⇒ token、token 路徑 byte-identical
  零回歸**）；加新單位＝加字串，不需 migration。
- **圖表**：既有 cost-based 圖自動涵蓋新單位、不用改；原生單位只在「單一模型/端點」明細出現。
- **配額**：成本制配額（階段 33）以 USD 為共同分母統一治理所有端點——補上非 token 端點（realtime 長連線等）
  「永遠碰不到月配額」的缺口。
- **誠實邊界**：未定價呼叫花費視為 0 且**不被擋**、逐筆顯示「未定價」不可當 0——系統對「沒定價」誠實，不假裝
  花了錢、也不視為無限（`PriceList` 是計費唯一真理，要治理得先補價）。

## 投影到三觀點

- **principles**：原則 1（額度綁分配、可調整可收回）+ 原則 2（可追蹤性）+ 原則 7（資料驅動、litellm 只給建議價）。
- **vision**：〈架構〉計費段。
- **history**：計費一般化與成本制配額（階段 29/33，見 `completed-phases-detail.md`）。

## 指回

- `concepts/加一個同形態端點應該等於加一筆資料.md`（Meter 是端點三軸之一）
- experience「dev SQLite / prod Postgres」（真實牌價會推翻「憑種類想當然」的計費假設——`print(model_cost)` 前置到 spec 層）。
