import { beforeEach, describe, expect, it } from "vitest";

import {
  ApiError,
  clearAuth,
  getRefreshToken,
  getToken,
  setRefreshToken,
  setToken,
} from "./api";

describe("auth helpers", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("setToken writes and getToken reads", () => {
    setToken("abc");
    expect(getToken()).toBe("abc");
  });

  it("setToken(null) clears the token", () => {
    setToken("abc");
    setToken(null);
    expect(getToken()).toBeNull();
  });

  it("setRefreshToken / getRefreshToken round-trip", () => {
    setRefreshToken("r1");
    expect(getRefreshToken()).toBe("r1");
  });

  it("clearAuth removes both tokens", () => {
    setToken("a");
    setRefreshToken("r");
    clearAuth();
    expect(getToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });
});

describe("ApiError", () => {
  it("stores status, message and optional code", () => {
    const err = new ApiError(400, "boom", "bad_thing");
    expect(err.status).toBe(400);
    expect(err.message).toBe("boom");
    expect(err.code).toBe("bad_thing");
    expect(err).toBeInstanceOf(Error);
  });

  it("allows omitting the code", () => {
    const err = new ApiError(500, "server down");
    expect(err.code).toBeUndefined();
  });
});
