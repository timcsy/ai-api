# Phase 1 Data Model: 應用分頁

**無 schema 變更、無新表、無 migration。** 只在既有 `/me/allocations` 序列化加一個唯讀衍生欄；應用清單為前端靜態。

## 既有實體：`Allocation`（序列化加衍生欄）

`GET /me/allocations` 每筆既有：`id`、`resource_model`、`display_name`、`status`、`price`、`token_prefix`…
**新增唯讀衍生欄**：
- `agent_compatible: bool` —— 該分配的模型可否走 Responses（Codex/Agent）。
  計算：載入 `resource_model → ModelCatalog.capabilities`，`responses_support.get_support(caps)["state"] == "available"`。
  模型不在 catalog（orphan）或 unknown/unavailable → `false`。

## 概念實體：應用（前端靜態，v1）

不落 DB。v1 清單只有一筆：
```text
Application(Codex) = {
  id: "codex",
  name: "Codex",
  blurb: "OpenAI 的 agent CLI / IDE 擴充 / 桌面 App",
  requires: "agent_compatible",        # 需要 Agent 相容（Responses）模型
  install: device-flow 一鍵（既有 CodexInstallCard）,
  interfaces: [
    { key:"cli",      label:"CLI",            how:"一鍵安裝（含下載 + 設定）",        auto:true  },
    { key:"vscode",   label:"VS Code 擴充",   how:"marketplace 連結（或可選順手裝）",  auto:"maybe" },
    { key:"desktop",  label:"桌面 App",       how:"下載連結，裝好免再設定（共用設定）", auto:false },
    { key:"otherIde", label:"Cursor/JetBrains", how:"各自 marketplace 連結，免再設定", auto:false },
  ],
  webNote: "網頁版 chatgpt.com/codex：✗ 不適用（綁 ChatGPT 帳號）",
}
```

## 卡片狀態（衍生自 /me/allocations）

```text
agentAllocs = allocations.filter(a => a.status === "active" && a.agent_compatible)
status:
  - agentAllocs.length > 0 → "可用"：可一鍵設定 + 建金鑰捷徑（picker = agentAllocs，預選）
  - agentAllocs.length === 0 → "尚不可用"：顯示指引（去模型目錄領取 / 請 admin 授權），不開建立流程
```

## 建金鑰捷徑（重用既有，無新實體）

`POST /me/credentials`（既有）body `{ name: "Codex"(預設可改), allocation_ids: [agentAllocs…] }` → token 顯示一次。
**不變式**：捷徑送出的 `allocation_ids` MUST ⊆ `agent_compatible` 分配；非相容分配不得納入。

## 不變式

- `agent_compatible` 為唯讀衍生，MUST NOT 寫回 DB、MUST NOT 新增欄/表。
- 建金鑰捷徑 scope MUST 只含 Agent 相容分配（SC-002）。
- `CodexInstallCard` 上線後 MUST 只出現在 `/apps`（單一所在地，SC-004）。
