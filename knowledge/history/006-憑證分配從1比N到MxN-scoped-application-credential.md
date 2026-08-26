# 006：憑證↔分配從 1:N 到 M:N（scoped application credential）
> 日期：2026-06-05

## 轉移
- 舊（superseded）：階段 18（migration 0015）`Credential` 以 `allocation_id` 綁**單一**分配 = 單一 model
  （per-device 的 1:N 是「一分配掛多把憑證」，但每把仍只綁那一筆分配）。
- 新（spec 030 / 階段 20，migration 0017）：`Credential` 去 `allocation_id`、加 `member_id` + 新
  `CredentialAllocation` join 表（`UNIQUE(credential_id, resource_model)`）；憑證升為**可命名的 scoped
  application credential**，scope = 一組分配，呼叫依 request 的 model 歸戶到對應分配。

## 為什麼變
一個應用常要用多個 model（Codex 切 `/model`、agent 同時 chat + embedding）；舊模型下使用者得為每個 model
各建一把 token，Codex `auth.json` 只放一把、切 model 就 403。「一 token 一 model」在業界罕見（過度細粒度）。
安全落地的關鍵是先找到一句「**舊模型 = 新模型的特例**」（scope 只含一筆分配的 key）——講得出這句，migration
（把既有列搬成 scope 一列）與零回歸測試的形狀就清楚了，原則措辭也得以**一般化而非重寫**。

## 狀態
✅ 已採用。原則 1（憑證隔離）由「一憑證綁一分配」一般化為 M:N；「撤銷單一憑證不影響其他」在此名副其實。
既有單分配 token 零回歸（以 Postgres 整合測試固化）。attenuation（不提權）同時落地。
