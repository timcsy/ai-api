// Maps backend raw status/actor values to Traditional Chinese display labels.
// Unknown values are returned as-is so nothing is silently hidden.

const STATUS_LABELS: Record<string, string> = {
  active: "使用中",
  paused: "已暫停",
  quarantined: "已隔離",
  revoked: "已撤回",
  expired: "已過期",
  deprecated: "已淘汰",
  disabled: "已停用",
};

export function statusLabel(s: string): string {
  return STATUS_LABELS[s] ?? s;
}

const ACTOR_LABELS: Record<string, string> = {
  system: "系統",
  admin: "管理員",
  member: "成員",
  anonymous: "匿名",
};

export function actorLabel(s: string): string {
  return ACTOR_LABELS[s] ?? s;
}

// default_access enum → display. Code keeps "open"/"restricted"; UI shows 中文.
const ACCESS_LABELS: Record<string, string> = {
  open: "開放",
  restricted: "限定",
};

export function accessLabel(s: string): string {
  return ACCESS_LABELS[s] ?? s;
}

// model family — only the generic "general" reads oddly in English; model-named
// families (gpt-4o, claude-3, …) stay as-is.
const FAMILY_LABELS: Record<string, string> = {
  general: "通用",
};

export function familyLabel(s: string): string {
  return FAMILY_LABELS[s] ?? s;
}

// AuditEventType enum → plain-language 繁中. Unknown values returned as-is.
const EVENT_LABELS: Record<string, string> = {
  login_success: "登入成功",
  login_failure: "登入失敗",
  logout: "登出",
  member_created: "建立成員",
  member_disabled: "停用成員",
  member_deleted: "刪除成員",
  whitelist_added: "加入白名單",
  whitelist_removed: "移除白名單",
  rule_added: "新增規則",
  rule_removed: "移除規則",
  restriction_added: "新增限制",
  restriction_removed: "移除限制",
  password_changed: "變更密碼",
  invitation_issued: "發出邀請",
  invitation_used: "使用邀請",
  allocation_quarantined: "分配已隔離",
  allocation_unquarantined: "分配解除隔離",
  anomaly_detector_run: "異常偵測器執行",
  quota_pool_rebalanced: "配額池重新平衡",
  rebalance_failed: "重新平衡失敗",
  pool_exhausted_by_reserved: "配額池被保留額耗盡",
  pool_idle: "配額池閒置",
  member_promoted: "成員升為管理員",
  member_demoted: "成員降為一般",
  allocation_token_rotated: "分配 token 輪替",
  provider_credential_created: "建立供應商憑證",
  provider_credential_rotated: "輪替供應商憑證",
  provider_credential_disabled: "停用供應商憑證",
  provider_credential_used_first_time: "供應商憑證首次使用",
  member_tag_added: "加標籤",
  member_tag_removed: "移除標籤",
  member_tag_bulk_added: "批次加標籤",
  model_access_policy_updated: "更新模型存取規則",
  self_service_claimed: "自助領取",
  self_service_reclaim_locked: "自助領取鎖定",
  self_service_unlocked: "自助領取解鎖",
  price_version_added: "新增價格版本",
  allocation_paused: "分配已暫停",
  allocation_resumed: "分配已恢復",
  responses_upstream_error_burst: "responses 上游錯誤暴增",
  provider_credential_auth_failed: "供應商憑證驗證失敗",
  credential_added: "新增金鑰",
  credential_revoked: "撤回金鑰",
  device_authorization_approved: "裝置授權核准",
  device_authorization_denied: "裝置授權拒絕",
  credential_scope_added: "新增金鑰範圍",
  credential_scope_removed: "移除金鑰範圍",
  credential_renamed: "金鑰改名",
  responses_tested: "responses 測試",
  responses_support_overridden: "responses 可用性手動覆寫",
};

export function eventLabel(s: string): string {
  return EVENT_LABELS[s] ?? s;
}
