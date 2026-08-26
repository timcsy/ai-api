# 憑證是應用金鑰，其單位是「分配」而非 token

**可判斷主張**：任何拿一段文字問「這是不是一把可命名、可用一組分配（≥1）、每次呼叫依 request 的
model 歸戶到對應分配、且撤銷單把不影響其他的 key？」——是，就屬這個概念；若那段文字把「額度/歸戶/
唯一性」綁在 token 或單一 model 上，就是它的反例（過時模型）。

## 一句話

credential ↔ allocation 是**多對多**：憑證是使用者可命名的應用 key，scope = 一組分配；額度、歸戶、
可追蹤性全綁在**分配**層，token 只是「能用哪些分配」的存取方式。

## 為什麼是它（剪枝力）

- 一個應用常要用多個 model（Codex 切 `/model`、agent 同時 chat + embedding）。「一 token 一 model」在
  業界罕見（過度細粒度）、且 Codex `auth.json` 只放一把 key，切 model 就 403。
- 約束 `UNIQUE(credential_id, resource_model)`：同一把 key 內 model 不得重複，否則 `(token, model)` 無法唯一
  決定分配、歸戶有歧義。
- **attenuation（不提權）**：一把 key 的 scope 只能含擁有者已被授予的分配——打包既有授權、不創造新權限。
- 舊模型是新模型的**特例**（scope 只含一筆分配）；migration 只是把既有列搬成 scope 一列 → 零回歸。

## 投影到三觀點

- **principles**：直接是原則 1（憑證隔離）的一般化；attenuation 是原則 4（轉分配需顯式允許）；歸戶不變式
  服務原則 2（可追蹤性）。
- **vision**：〈核心想法〉的「應用金鑰」、〈架構〉的前置 pipeline；OAuth/device-flow 都只是「發這把 key 的 UX」。
- **history / data-model**：`Credential` 去 `allocation_id`、加 `member_id` + `CredentialAllocation` join
  （migration 0017）；階段 18 的 1:N per-device 是中途站。

## 指回

- `history/006-憑證分配從1比N到MxN-scoped-application-credential.md`（因果轉移）
- `history/001-...` 的 attenuation 精神；`concepts/可見性等於供給存在交集授權允許.md`
- 業界對照：GitHub fine-grained PAT、service account、Azure APIM subscription、OAuth2 scopes。
