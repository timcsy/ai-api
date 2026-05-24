import * as React from "react";
import type { QueryClient } from "@tanstack/react-query";

import { api, UNAUTHORIZED_EVENT } from "@/lib/api-client";

export type Member = {
  id: string;
  email: string;
  display_name?: string | null;
  provider?: string;
};

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  status: AuthStatus;
  member: Member | null;
  login(email: string, password: string): Promise<void>;
  loginGoogle(): void;
  logout(): Promise<void>;
  refresh(): Promise<void>;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function AuthProvider({
  children,
  queryClient,
}: {
  children: React.ReactNode;
  queryClient?: QueryClient;
}) {
  const [status, setStatus] = React.useState<AuthStatus>("loading");
  const [member, setMember] = React.useState<Member | null>(null);

  const refresh = React.useCallback(async () => {
    try {
      const m = await api<Member>("/me");
      setMember(m);
      setStatus("authenticated");
    } catch {
      setMember(null);
      setStatus("unauthenticated");
    }
  }, []);

  React.useEffect(() => {
    void refresh();
    const onUnauth = () => {
      setMember(null);
      setStatus("unauthenticated");
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauth);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauth);
  }, [refresh]);

  const login = React.useCallback(
    async (email: string, password: string) => {
      await api<unknown>("/auth/local/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      await refresh();
    },
    [refresh],
  );

  const loginGoogle = React.useCallback(() => {
    // Redirect to backend-initiated OIDC flow.
    window.location.href = "/auth/oidc/start";
  }, []);

  const logout = React.useCallback(async () => {
    try {
      await api<unknown>("/auth/logout", { method: "POST" });
    } finally {
      // Clear TanStack Query cache so the next member won't see the prior
      // member's data (FR-027).
      queryClient?.clear();
      setMember(null);
      setStatus("unauthenticated");
    }
  }, [queryClient]);

  const value = React.useMemo<AuthContextValue>(
    () => ({ status, member, login, loginGoogle, logout, refresh }),
    [status, member, login, loginGoogle, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
