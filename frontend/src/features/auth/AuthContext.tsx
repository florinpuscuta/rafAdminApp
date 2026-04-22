import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  clearAuth,
  getRefreshToken,
  getToken,
  setRefreshToken,
  setToken,
} from "../../shared/api";
import { setSentryUser } from "../../sentry";
import * as authApi from "./api";
import type { AuthResponse, LoginPayload, SignupPayload, User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  signup: (payload: SignupPayload) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then((u) => {
        setUser(u);
        setSentryUser({ id: u.id, email: u.email, tenantId: u.tenantId });
      })
      .catch(() => clearAuth())
      .finally(() => setLoading(false));
  }, []);

  const applyAuth = useCallback((resp: AuthResponse) => {
    setToken(resp.accessToken);
    setRefreshToken(resp.refreshToken);
    setUser(resp.user);
    setSentryUser({
      id: resp.user.id,
      email: resp.user.email,
      tenantId: resp.user.tenantId,
    });
  }, []);

  const login = useCallback(
    async (payload: LoginPayload) => {
      const resp = await authApi.login(payload);
      applyAuth(resp);
    },
    [applyAuth],
  );

  const signup = useCallback(
    async (payload: SignupPayload) => {
      const resp = await authApi.signup(payload);
      applyAuth(resp);
    },
    [applyAuth],
  );

  const logout = useCallback(async () => {
    const refresh = getRefreshToken();
    if (refresh) {
      try {
        await authApi.logout(refresh);
      } catch {
        /* best-effort: chiar dacă revocarea pe server eșuează, curățăm client-ul */
      }
    }
    clearAuth();
    setUser(null);
    setSentryUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    if (!getToken()) return;
    try {
      const u = await authApi.me();
      setUser(u);
    } catch {
      clearAuth();
      setUser(null);
    }
  }, []);

  const value = useMemo<AuthState>(
    () => ({ user, loading, login, signup, logout, refreshUser }),
    [user, loading, login, signup, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
