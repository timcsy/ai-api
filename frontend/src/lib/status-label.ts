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
