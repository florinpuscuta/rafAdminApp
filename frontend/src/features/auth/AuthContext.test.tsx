import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "./AuthContext";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const sampleUser = {
  id: "u1",
  email: "owner@example.com",
  role: "admin",
  tenantId: "t1",
  active: true,
  emailVerified: true,
  createdAt: "2026-01-01T00:00:00Z",
  lastLoginAt: null,
};

const sampleTenant = { id: "t1", name: "Acme", createdAt: "2026-01-01T00:00:00Z" };

const sampleAuthResponse = {
  accessToken: "access-token",
  refreshToken: "refresh-token",
  user: sampleUser,
  tenant: sampleTenant,
};

function Consumer() {
  const { user, loading, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="loading">{loading ? "yes" : "no"}</span>
      <span data-testid="user">{user ? user.email : "none"}</span>
      <button onClick={() => void login({ email: "a@b.c", password: "parola1234" })}>
        Login
      </button>
      <button onClick={() => void logout()}>Logout</button>
    </div>
  );
}

describe("AuthContext", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });
  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("starts with loading=true, no user, when no token in storage", async () => {
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );
    // Cu token lipsă, efectul inițial seteaza loading=false sincron
    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("no"));
    expect(screen.getByTestId("user")).toHaveTextContent("none");
  });

  it("hydrates user from /me when token exists on mount", async () => {
    localStorage.setItem("adeplast_token", "existing-access");
    const fetchMock = vi.fn(async (url: string) => {
      if (url.endsWith("/api/auth/me")) return json(sampleUser);
      return new Response("", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("user")).toHaveTextContent("owner@example.com"),
    );
    expect(screen.getByTestId("loading")).toHaveTextContent("no");
  });

  it("clearAuth on /me failure during hydration", async () => {
    localStorage.setItem("adeplast_token", "invalid");
    localStorage.setItem("adeplast_refresh", "invalid-ref");
    const fetchMock = vi.fn(async () => new Response("", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("none"));
    expect(screen.getByTestId("loading")).toHaveTextContent("no");
    expect(localStorage.getItem("adeplast_token")).toBeNull();
    expect(localStorage.getItem("adeplast_refresh")).toBeNull();
  });

  it("login stores tokens and populates user", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (url: string) => {
      if (url.endsWith("/api/auth/login")) return json(sampleAuthResponse);
      return new Response("", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("loading")).toHaveTextContent("no"));

    await user.click(screen.getByRole("button", { name: "Login" }));

    await waitFor(() =>
      expect(screen.getByTestId("user")).toHaveTextContent("owner@example.com"),
    );
    expect(localStorage.getItem("adeplast_token")).toBe("access-token");
    expect(localStorage.getItem("adeplast_refresh")).toBe("refresh-token");
  });

  it("logout revokes refresh on server and clears client state", async () => {
    const user = userEvent.setup();
    localStorage.setItem("adeplast_token", "tok");
    localStorage.setItem("adeplast_refresh", "ref");

    const fetchMock = vi.fn(async (url: string) => {
      if (url.endsWith("/api/auth/me")) return json(sampleUser);
      if (url.endsWith("/api/auth/logout")) return json({});
      return new Response("", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("user")).toHaveTextContent("owner@example.com"),
    );

    await user.click(screen.getByRole("button", { name: "Logout" }));

    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("none"));
    expect(localStorage.getItem("adeplast_token")).toBeNull();
    expect(localStorage.getItem("adeplast_refresh")).toBeNull();

    // Logout-ul a trimis un POST la /api/auth/logout cu refresh
    const logoutCall = fetchMock.mock.calls.find(
      (c) => typeof c[0] === "string" && (c[0] as string).endsWith("/api/auth/logout"),
    );
    expect(logoutCall).toBeDefined();
  });

  it("logout still clears client state when server revoke fails", async () => {
    const user = userEvent.setup();
    localStorage.setItem("adeplast_token", "tok");
    localStorage.setItem("adeplast_refresh", "ref");

    const fetchMock = vi.fn(async (url: string) => {
      if (url.endsWith("/api/auth/me")) return json(sampleUser);
      if (url.endsWith("/api/auth/logout")) return new Response("", { status: 500 });
      return new Response("", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("user")).toHaveTextContent("owner@example.com"),
    );

    await user.click(screen.getByRole("button", { name: "Logout" }));

    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("none"));
    expect(localStorage.getItem("adeplast_token")).toBeNull();
  });

  it("useAuth throws outside AuthProvider", () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    function Orphan() {
      useAuth();
      return null;
    }
    expect(() => render(<Orphan />)).toThrow(/AuthProvider/);
    errSpy.mockRestore();
  });
});
