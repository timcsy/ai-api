/** Single source of truth for the gateway call endpoint shown to members.
 * The browser origin is what the user can actually reach (dev: Vite proxies
 * /v1; prod: same ingress). For cross-host hints, fall back to the
 * server-provided member.gateway_base_url at the call site. */
export function apiBaseUrl(): string {
  return `${window.location.origin}/v1`;
}
