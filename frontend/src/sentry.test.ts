import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock @sentry/react — exports sunt frozen și nu pot fi spy-uite direct.
// Mock-ul e folosit atât pentru static cât și dynamic import (Vitest rezolvă
// amândouă prin același module cache).
vi.mock("@sentry/react", () => ({
  init: vi.fn(),
  setUser: vi.fn(),
  setTag: vi.fn(),
}));

import * as SentrySdk from "@sentry/react";

describe("initSentry (lazy-load)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    delete (window as unknown as { Sentry?: unknown }).Sentry;
    vi.resetModules();
  });
  afterEach(() => {
    delete (window as unknown as { Sentry?: unknown }).Sentry;
  });

  it("no-ops when no DSN provided (no dynamic import, no init)", async () => {
    const { initSentry } = await import("./sentry");
    initSentry();
    // Aștept un tick pentru orice promise async.
    await Promise.resolve();
    expect(SentrySdk.init).not.toHaveBeenCalled();
    expect((window as unknown as { Sentry?: unknown }).Sentry).toBeUndefined();
  });

  it("initializes with DSN and exposes SDK on window (after dynamic import resolves)", async () => {
    const { initSentry } = await import("./sentry");
    initSentry({ dsn: "https://fake@sentry.io/123", environment: "staging", release: "1.0.0" });
    // Așteaptă ca dynamic import-ul + then-ul să se rezolve
    await new Promise((r) => setTimeout(r, 0));
    expect(SentrySdk.init).toHaveBeenCalledTimes(1);
    const cfg = (SentrySdk.init as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as Record<string, unknown>;
    expect(cfg.dsn).toBe("https://fake@sentry.io/123");
    expect(cfg.environment).toBe("staging");
    expect(cfg.release).toBe("1.0.0");
    expect((window as unknown as { Sentry?: unknown }).Sentry).toBeDefined();
  });

  it("initializes only once (idempotent)", async () => {
    const { initSentry } = await import("./sentry");
    initSentry({ dsn: "https://fake@sentry.io/123" });
    initSentry({ dsn: "https://fake@sentry.io/123" });
    await new Promise((r) => setTimeout(r, 0));
    expect(SentrySdk.init).toHaveBeenCalledTimes(1);
  });

  it("setSentryUser is a no-op when Sentry not initialized", async () => {
    const { setSentryUser } = await import("./sentry");
    setSentryUser({ id: "u1", email: "a@b.c", tenantId: "t1" });
    await new Promise((r) => setTimeout(r, 0));
    expect(SentrySdk.setUser).not.toHaveBeenCalled();
  });

  it("setSentryUser forwards identity after init", async () => {
    const { initSentry, setSentryUser } = await import("./sentry");
    initSentry({ dsn: "https://fake@sentry.io/123" });
    setSentryUser({ id: "u1", email: "a@b.c", tenantId: "t1" });
    await new Promise((r) => setTimeout(r, 0));
    expect(SentrySdk.setUser).toHaveBeenCalledWith({ id: "u1", email: "a@b.c" });
    expect(SentrySdk.setTag).toHaveBeenCalledWith("tenant_id", "t1");
  });

  it("setSentryUser(null) clears identity", async () => {
    const { initSentry, setSentryUser } = await import("./sentry");
    initSentry({ dsn: "https://fake@sentry.io/123" });
    setSentryUser(null);
    await new Promise((r) => setTimeout(r, 0));
    expect(SentrySdk.setUser).toHaveBeenCalledWith(null);
    expect(SentrySdk.setTag).toHaveBeenCalledWith("tenant_id", null);
  });
});
