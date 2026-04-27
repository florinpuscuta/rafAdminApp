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
import { usePrivacy } from "../../shared/ui/PrivacyProvider";
import * as authApi from "./api";
import type {
  AuthResponse,
  Capabilities,
  LoginPayload,
  SignupPayload,
  User,
} from "./types";

interface AuthState {
  user: User | null;
  capabilities: Capabilities | null;
  loading: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  signup: (payload: SignupPayload) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  /** True dacă rolul curent are acces la modulul cerut (sau e admin wildcard). */
  canAccess: (moduleName: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const { setForced } = usePrivacy();

  // Pentru rolul `viewer` forțăm modul confidențial (ascunderea agenților).
  // Flag-ul `forced` din PrivacyProvider face toggle-ul din Settings no-op
  // și menține mereu ON, indiferent de localStorage.
  useEffect(() => {
    setForced(user?.roleV2 === "viewer");
  }, [user?.roleV2, setForced]);

  // Helper: aducerea capabilităților nu blochează aplicația dacă pică
  // (frontend-ul cade pe `user.role === "admin"` ca fallback).
  const fetchCapabilities = useCallback(async () => {
    try {
      const caps = await authApi.capabilities();
      setCapabilities(caps);
    } catch {
      setCapabilities(null);
    }
  }, []);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then(async (u) => {
        setUser(u);
        setSentryUser({ id: u.id, email: u.email, tenantId: u.tenantId });
        await fetchCapabilities();
      })
      .catch(() => clearAuth())
      .finally(() => setLoading(false));
  }, [fetchCapabilities]);

  const applyAuth = useCallback(
    (resp: AuthResponse) => {
      setToken(resp.accessToken);
      setRefreshToken(resp.refreshToken);
      setUser(resp.user);
      setSentryUser({
        id: resp.user.id,
        email: resp.user.email,
        tenantId: resp.user.tenantId,
      });
      // După login/signup, aducem capabilităţile imediat (non-blocking).
      void fetchCapabilities();
    },
    [fetchCapabilities],
  );

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
    setCapabilities(null);
    setSentryUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    if (!getToken()) return;
    try {
      const u = await authApi.me();
      setUser(u);
      await fetchCapabilities();
    } catch {
      clearAuth();
      setUser(null);
      setCapabilities(null);
    }
  }, [fetchCapabilities]);

  const canAccess = useCallback(
    (moduleName: string): boolean => {
      // Fallback safety: dacă n-am încă capabilities (race la load), permite
      // adminul legacy să vadă tot. Restul rolurilor primesc default deny.
      if (!capabilities) {
        return user?.role === "admin";
      }
      const mods = capabilities.modules;
      return mods.includes("*") || mods.includes(moduleName);
    },
    [capabilities, user],
  );

  const value = useMemo<AuthState>(
    () => ({
      user, capabilities, loading,
      login, signup, logout, refreshUser, canAccess,
    }),
    [user, capabilities, loading, login, signup, logout, refreshUser, canAccess],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
