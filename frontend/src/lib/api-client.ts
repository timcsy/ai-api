/**
 * Minimal fetch wrapper for the AI API backend.
 *
 * - Always sends `credentials: 'include'` so the session cookie travels.
 * - On 401 dispatches a `api:unauthorized` event so the AuthContext can
 *   reset state without every call-site having to handle it.
 */
export const UNAUTHORIZED_EVENT = "api:unauthorized";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function csrfToken(): string {
  return document.cookie.match(/aiapi_csrf=([^;]+)/)?.[1] ?? "";
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  // Auto-attach CSRF token for state-changing requests (the backend's
  // require_csrf compares this header to the aiapi_csrf cookie). Admin
  // endpoints authenticate via X-Admin-Token and simply ignore it.
  const csrfHeaders: Record<string, string> =
    method === "GET" ? {} : { "X-CSRF-Token": csrfToken() };
  const res = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...csrfHeaders,
      ...(init.headers ?? {}),
    },
    ...init,
  });

  if (!res.ok) {
    type ErrEnvelope = { code?: string; message?: string };
    let body: { error?: ErrEnvelope; detail?: { error?: ErrEnvelope } } = {};
    try {
      body = await res.json();
    } catch {
      // body may not be JSON (e.g. proxy 5xx)
    }
    // Two shapes in this app: proxy returns `{error}`, FastAPI HTTPException
    // wraps it as `{detail: {error}}`. Accept either.
    const err = body.error ?? body.detail?.error;
    const code = err?.code ?? "unknown";
    const message = err?.message ?? res.statusText;

    if (res.status === 401) {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    throw new ApiError(res.status, code, message);
  }

  // 204 No Content — return undefined
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}
