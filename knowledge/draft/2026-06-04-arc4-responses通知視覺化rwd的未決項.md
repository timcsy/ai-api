# Arc 4（Responses/email 通知/tag rollup/視覺化/RWD/成員圖表/per-device）未決項快照

> 怎麼冒出來的：migrate 從 arc-4〈開放〉搬下（截至 `c2e75a1`，2026-06-04）。

- 〔仍開放〕**多 replica 去重的 N 封信**：每窗每型別至多 N 封（N=replica 數）實務可接受；未量化上限、
  未定義 scale-out 是否需跨 replica 協調（共享 lock / 單一 leader）。
- 〔仍開放〕**通知管道擴充**：`Notifier` interface 已為 LINE Bot / Web Push 預留，何時做/優先序未定。
- 〔部分閉合〕**圖表 v2 範圍**：allocation/member 詳情頁圖、配額燃燒投影、月底投影、PNG export 列 v2 無排程
  （per-allocation 圖已隨階段 18 提前落地一部分）。
- 〔已閉合→階段 19〕**device-flow（RFC 8628）**延至階段 19。
- 〔仍開放/邊界〕**320px 極窄裝置**：best-effort、不保證像素完美，崩版風險未有測試固化。
- 〔仍開放/YAGNI〕**tag 時間版本化**：明確延後；「學期中轉班需精確歷史歸屬」若出現再評估。
- 〔仍開放〕**litellm 對 Codex 逐欄保真的回歸監看**：以真機驗收收尾；(推測) litellm 升級改變 responses
  行為需重驗——此弧未記錄回歸監看機制細節。
