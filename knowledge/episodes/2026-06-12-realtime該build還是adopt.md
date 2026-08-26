# 2026-06-12 · realtime 該 build 還是 adopt（build-vs-adopt 判準升級）

## 為何（why）
階段 32 要做 `/v1/realtime` 即時字幕。litellm 也有 realtime——直覺會想「功能重疊、adopt 就好」。

## 怎麼（how / 為何這樣選）
盤點發現 litellm 的 realtime 是 **Proxy form / client 直連**，**音訊繞過 gateway** → 會失去「歸戶到分配」與
「即時撤回」，而這兩者正是平台的價值核心。於是把 build-vs-adopt 判準明確**升級**為「以**領域第一公民是否
同軸**判，非功能重疊度」：litellm 歸戶第一公民是 key/user/team，我們是「分配（member × model）」——同一件事、
不同世界觀。對已上線、已兌現價值的系統（原則 6 + 配額池 + 課堂 rollup 都建在「分配」上），門檻再升一級：
問題不是「它能不能做基本款」而是「遷過去重做值不值」——幾乎不值。決定：自寫薄雙向 relay（借 litellm
`RealTimeStreaming` **結構**、直接依賴 `websockets`、不經 litellm），計費/分配核心守在自己這邊。

## 用了哪些概念
[`concepts/功能重疊不等於該adopt判準是領域第一公民同不同軸.md`](../concepts/功能重疊不等於該adopt判準是領域第一公民同不同軸.md)；
「realtime 是能力軸非 mode」（讀 `supported_endpoints`）。

## 結果
`proxy/realtime.py` 薄 relay 上線（階段 32）；判準寫進原則 7 與 tombstones「整包改 LiteLLM Proxy」。真機探測還
揭露 Azure realtime WS 必須 `intent=transcription`、**不帶** `deployment=`。
