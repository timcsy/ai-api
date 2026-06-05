# Data Model：憑證 UI 收斂

## 無 schema 變更

本階段**不新增表、不新增欄、不新增 migration**。

## 沿用實體

- **應用金鑰（Credential，階段 20）**：`name` 欄位**已存在**；本階段只**允許更新 `name`**（純標籤），不動 `member_id`、scope（`CredentialAllocation`）、`token_fingerprint`、`revoked_at`、計費語意。
  - **不變式**：改名**不得**改變 token 解析、可用 model（scope）、狀態、歸戶。
  - **狀態**：`name` 可由擁有者（member 自助）或 admin 更新；改名留稽核。

## 稽核

- 新增 `AuditEventType.credential_renamed`（`Enum(..., native_enum=False)` 存 VARCHAR → **免 migration**）。改名時記（誰、何時、哪把、可選舊→新名）。
