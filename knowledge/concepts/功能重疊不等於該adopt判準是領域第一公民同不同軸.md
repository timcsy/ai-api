# 功能重疊 ≠ 該 adopt——判準是「領域第一公民同不同軸」

**可判斷主張**：拿一個 build-vs-adopt 決策問「它是憑『那套工具功能重疊度高』決定 adopt，還是憑『它的領域
第一公民和我們同不同軸』決定？」——後者屬這個概念；憑功能重疊度就 adopt，是反例。

## 一句話

一套外部系統能不能 adopt，看的不是它會不會做這件事（通常會），而是它的「第一公民」和我們的核心抽象是不是
同一個世界觀——以及對已兌現價值的核心，遷過去重做值不值。

## 為什麼是它（剪枝力）

- litellm 的歸戶第一公民是 **key / user / team**；我們是**分配（member × model）**——同一件事、不同世界觀。
- **形態層**：litellm library form ＝核心穩定、邊緣快變、單一 adapter（採用）；litellm **Proxy form** 會讓快變的
  litellm 變成核心、方向反了（否決整包改 Proxy）。
- **realtime 案例**：litellm 的 realtime 是 Proxy form / client 直連、**音訊繞過 gateway** → 失去「歸戶到分配」與
  「即時撤回」（正是平台價值核心）→ build 薄 relay（借其 `RealTimeStreaming` **結構**、不經 litellm）。
- **門檻升級**：對已上線、已兌現價值的系統（原則 6 + 配額池 + 課堂 rollup 都建在「分配」上），問題不是「它能不能
  做基本款」而是「遷過去重做值不值」——幾乎不值。
- **形態可進退**：選對形態後，「採用」與「自製」可並存、可隨需求進退（litellm 一進一出再進即例）。

## 投影到三觀點

- **principles**：原則 7（build-vs-adopt 判準、適配層）+ 原則 5（雙核心並行必 drift）。
- **vision**：〈架構〉litellm library-only + realtime 例外。
- **history**：`001-litellm形態從ProxyServer到library-only.md`；`tombstones.md`（整包改 LiteLLM Proxy）。

## 指回

- `history/001-litellm形態從ProxyServer到library-only.md`、`history/tombstones.md`
- experience「採用外部工具前先確認形態並實測能力邊界」。
