# 014：叢集拓撲從「tew（+ccsh 雙叢集並存）」到「ccsh 唯一」
> 日期：2026-08-07

## 轉移
- 舊（superseded）：ai-api 曾在 **tew + ccsh 雙叢集並存**（遷入 ccsh 觸發 2026-06-29 的 last_used_at 事故，
  見 `010-*`）；此期間 experience/vision 常見「tew/ccsh 皆上線」。
- 新（2026-08-07）：ai-api 從 **k3s-tew 全數退役**——ns `ai-ccsh`（含自帶 Postgres/PVC）連同 helm release
  一併移除、**歷史資料按維護者指示直接刪不保留**；`ccsh`（`ai.ccsh.tn.edu.tw`）自此為**唯一部署**，
  `ai-ccsh.tew.tw` 失效（DNS 由維護者自撤）。

## 為什麼變
維護者決策收斂到單一叢集。**rev 編號失效**：舊敘述的 rev 數字是**當時 tew 的 helm 計數**、tew 退役後失效；
ccsh 為獨立計數（截至 `9ec5eea` 為 **ccsh helm rev 25**）。故 Arc 8 多數條目並記「ccsh rev N / tew rev M」
——**往後只認 ccsh 計數**，讀舊 rev 數字須知它指的是已退役叢集。

## 狀態
✅ 已採用。⚰️ tew 部署退役（不保留歷史資料）。見 MEMORY `project_deployment` / `reference_k8s_clusters`。
