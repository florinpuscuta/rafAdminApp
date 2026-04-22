import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, clearAuth, setRefreshToken, setToken } from "./api";

function mockJsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

describe("apiFetch — 401 refresh flow", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });
  afterEach(() => {
    clearAuth();
    vi.restoreAllMocks();
  });

  it("returns data normally when server returns 200", async () => {
    setToken("access-A");
    const fetchMock = vi.fn(async () => mockJsonResponse({ hello: "world" }));
    vi.stubGlobal("fetch", fetchMock);

    const out = await apiFetch<{ hello: string }>("/api/me");
    expect(out).toEqual({ hello: "world" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    // Auth header incluse
    const call = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    const headers = call[1].headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer access-A");
  });

  it("refreshes on 401 and retries the original request", async () => {
    setToken("expired-token");
    setRefreshToken("refresh-abc");

    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("/api/auth/refresh")) {
        return mockJsonResponse({ accessToken: "new-access", refreshToken: "new-refresh" });
      }
      // Primul call → 401; după refresh header-ul e "Bearer new-access" → 200
      // Distingem după stadiul în care suntem (prin număr de call-uri).
      const callsSoFar = fetchMock.mock.calls.length;
      if (callsSoFar === 1) return new Response("", { status: 401 });
      return mockJsonResponse({ ok: true, retried: true });
    });
    vi.stubGlobal("fetch", fetchMock);

    const out = await apiFetch<{ ok: boolean; retried: boolean }>("/api/resource");
    expect(out).toEqual({ ok: true, retried: true });
    // 3 fetch-uri: original 401, refresh, retry
    expect(fetchMock).toHaveBeenCalledTimes(3);

    // Al doilea fetch e /api/auth/refresh cu refresh body
    const secondCall = fetchMock.mock.calls[1] as unknown as [string, RequestInit];
    expect(secondCall[0]).toContain("/api/auth/refresh");
    expect(secondCall[1].method).toBe("POST");

    // Al treilea fetch folosește noul access token
    const thirdCall = fetchMock.mock.calls[2] as unknown as [string, RequestInit];
    const headers = thirdCall[1].headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer new-access");
  });

  it("clears auth when refresh itself fails", async () => {
    setToken("expired");
    setRefreshToken("bad-refresh");

    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("/api/auth/refresh")) {
        return new Response("", { status: 401 });  // refresh respins
      }
      return new Response("", { status: 401 });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/api/resource")).rejects.toBeInstanceOf(ApiError);
    // Tokens cleared după refresh eșuat
    expect(localStorage.getItem("adeplast_token")).toBeNull();
    expect(localStorage.getItem("adeplast_refresh")).toBeNull();
  });

  it("does not attempt refresh for /api/auth/* paths (avoid loops)", async () => {
    setToken("tok");
    setRefreshToken("ref");
    const fetchMock = vi.fn(async () => new Response("", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/api/auth/login", { method: "POST" })).rejects.toBeInstanceOf(ApiError);
    // Un singur call — nu refresh, nu retry
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("parses 429 body and exposes retryAfter on ApiError", async () => {
    setToken("tok");
    const fetchMock = vi.fn(async () =>
      mockJsonResponse(
        { detail: { code: "rate_limited", message: "Prea multe cereri", retryAfter: 42 } },
        429,
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/api/auth/login", { method: "POST" })).rejects.toMatchObject({
      status: 429,
      code: "rate_limited",
      retryAfter: 42,
    });
  });

  it("handles 204 No Content as undefined", async () => {
    setToken("tok");
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    const out = await apiFetch("/api/resource", { method: "DELETE" });
    expect(out).toBeUndefined();
  });
});
