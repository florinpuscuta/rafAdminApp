const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "adeplast_token";
const REFRESH_KEY = "adeplast_refresh";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setRefreshToken(token: string | null): void {
  if (token) localStorage.setItem(REFRESH_KEY, token);
  else localStorage.removeItem(REFRESH_KEY);
}

export function clearAuth(): void {
  setToken(null);
  setRefreshToken(null);
}

export class ApiError extends Error {
  code?: string;
  status: number;
  /** Pentru 429 — secunde până la retry conform backend-ului / Retry-After header. */
  retryAfter?: number;

  constructor(status: number, message: string, code?: string, retryAfter?: number) {
    super(message);
    this.status = status;
    this.code = code;
    this.retryAfter = retryAfter;
  }
}

// Evită thundering herd la 401: un singur refresh în flight la un moment dat.
let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  try {
    const resp = await fetch(`${API_URL}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken: refresh }),
    });
    if (!resp.ok) {
      clearAuth();
      return false;
    }
    const data = (await resp.json()) as { accessToken: string; refreshToken: string };
    setToken(data.accessToken);
    setRefreshToken(data.refreshToken);
    return true;
  } catch {
    clearAuth();
    return false;
  }
}

async function parseErr(resp: Response): Promise<ApiError> {
  let code: string | undefined;
  let message = resp.statusText;
  let retryAfter: number | undefined;
  try {
    const data = await resp.json();
    if (data && typeof data === "object") {
      const detail = (data as { detail?: unknown }).detail;
      if (typeof detail === "string") {
        message = detail;
      } else if (detail && typeof detail === "object") {
        const d = detail as { code?: string; message?: string; retryAfter?: number };
        code = d.code;
        message = d.message ?? message;
        if (typeof d.retryAfter === "number") retryAfter = d.retryAfter;
      }
    }
  } catch {
    /* non-json body */
  }
  if (retryAfter == null) {
    const header = resp.headers.get("retry-after");
    if (header) {
      const n = Number(header);
      if (!Number.isNaN(n)) retryAfter = n;
    }
  }
  return new ApiError(resp.status, message, code, retryAfter);
}

async function rawFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  return fetch(`${API_URL}${path}`, { ...options, headers });
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let resp = await rawFetch(path, options);

  // Dacă access expiră: încearcă să refresh-uim o singură dată, apoi retry
  if (resp.status === 401 && getRefreshToken() && !path.startsWith("/api/auth/")) {
    if (!refreshPromise) refreshPromise = tryRefresh().finally(() => { refreshPromise = null; });
    const ok = await refreshPromise;
    if (ok) {
      resp = await rawFetch(path, options);
    }
  }

  if (!resp.ok) throw await parseErr(resp);
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}
