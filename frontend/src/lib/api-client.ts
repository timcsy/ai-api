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

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    ...init,
  });

  if (!res.ok) {
    let body: { error?: { code?: string; message?: string } } = {};
    try {
      body = await res.json();
    } catch {
      // body may not be JSON (e.g. proxy 5xx)
    }
    const code = body.error?.code ?? "unknown";
    const message = body.error?.message ?? res.statusText;

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
