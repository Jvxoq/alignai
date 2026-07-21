import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  signup,
  login,
  logout,
  deleteAccount,
  request,
  warmServices,
  getAccessToken,
  getRefreshToken,
  setTokens,
  clearTokens,
} from "../authApi";

function res({ ok = true, status = 200, body = {}, jsonThrows = false } = {}) {
  return {
    ok,
    status,
    json: async () => {
      if (jsonThrows) throw new SyntaxError("not json");
      return body;
    },
  };
}

beforeEach(() => {
  localStorage.clear();
  global.fetch = vi.fn();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("token storage helpers", () => {
  it("sets, reads, and clears both tokens", () => {
    setTokens("access-1", "refresh-1");
    expect(getAccessToken()).toBe("access-1");
    expect(getRefreshToken()).toBe("refresh-1");
    clearTokens();
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });
});

describe("signup", () => {
  it("stores tokens and returns data on success", async () => {
    fetch.mockResolvedValueOnce(res({ body: { access_token: "a", refresh_token: "r" } }));

    const data = await signup("u@example.com", "Password123!");

    expect(data).toEqual({ access_token: "a", refresh_token: "r" });
    expect(getAccessToken()).toBe("a");
    expect(getRefreshToken()).toBe("r");
    const [url, opts] = fetch.mock.calls[0];
    expect(url).toContain("/auth/signup");
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body)).toEqual({ email: "u@example.com", password: "Password123!" });
  });

  it("throws the string detail on a known error (e.g. 409)", async () => {
    fetch.mockResolvedValueOnce(res({ ok: false, status: 409, body: { detail: "Email already registered" } }));
    await expect(signup("u@example.com", "Password123!")).rejects.toThrow("Email already registered");
    expect(getAccessToken()).toBeNull();
  });

  it("flattens a 422 array detail into a readable message", async () => {
    fetch.mockResolvedValueOnce(
      res({
        ok: false,
        status: 422,
        body: { detail: [{ msg: "Password must be at most 72 bytes" }, { msg: "value is not a valid email" }] },
      })
    );
    await expect(signup("u@example.com", "x")).rejects.toThrow(
      "Password must be at most 72 bytes, value is not a valid email"
    );
  });

  it("falls back to a generic message when the body is not JSON", async () => {
    fetch.mockResolvedValueOnce(res({ ok: false, status: 500, jsonThrows: true }));
    await expect(signup("u@example.com", "Password123!")).rejects.toThrow("Signup failed");
  });
});

describe("login", () => {
  it("stores tokens on success", async () => {
    fetch.mockResolvedValueOnce(res({ body: { access_token: "a", refresh_token: "r" } }));
    await login("u@example.com", "Password123!");
    expect(getAccessToken()).toBe("a");
    expect(fetch.mock.calls[0][0]).toContain("/auth/login");
  });

  it("throws the string detail on 401", async () => {
    fetch.mockResolvedValueOnce(res({ ok: false, status: 401, body: { detail: "Invalid email or password" } }));
    await expect(login("u@example.com", "wrong")).rejects.toThrow("Invalid email or password");
  });

  it("falls back to a generic message when the body is not JSON", async () => {
    fetch.mockResolvedValueOnce(res({ ok: false, status: 500, jsonThrows: true }));
    await expect(login("u@example.com", "x")).rejects.toThrow("Login failed");
  });
});

describe("logout", () => {
  it("clears stored tokens", async () => {
    setTokens("a", "r");
    await logout();
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });
});

describe("warmServices", () => {
  it("pings the warm-up endpoint without a bearer token", async () => {
    fetch.mockResolvedValueOnce(res({ status: 200 }));
    await warmServices();
    const [url, opts] = fetch.mock.calls[0];
    expect(url).toContain("/health/warm");
    expect(opts.method).toBe("GET");
  });

  it("swallows errors so a failed pre-warm never breaks app load", async () => {
    fetch.mockRejectedValueOnce(new Error("network down"));
    await expect(warmServices()).resolves.toBeUndefined();
  });
});

describe("request", () => {
  it("attaches the bearer token and JSON content-type when a body is sent", async () => {
    setTokens("token-1", "r");
    fetch.mockResolvedValueOnce(res({ status: 200 }));

    await request("/auth/me", { method: "POST", body: JSON.stringify({ x: 1 }) });

    const [, opts] = fetch.mock.calls[0];
    expect(opts.headers.Authorization).toBe("Bearer token-1");
    expect(opts.headers["Content-Type"]).toBe("application/json");
  });

  it("omits the Authorization header when no token is stored", async () => {
    fetch.mockResolvedValueOnce(res({ status: 200 }));
    await request("/auth/me");
    expect(fetch.mock.calls[0][1].headers.Authorization).toBeUndefined();
  });

  it("refreshes once and retries with the new token on a 401", async () => {
    setTokens("stale", "refresh-1");
    fetch
      .mockResolvedValueOnce(res({ ok: false, status: 401 })) // original request
      .mockResolvedValueOnce(res({ body: { access_token: "fresh", refresh_token: "refresh-2" } })) // refresh
      .mockResolvedValueOnce(res({ status: 200 })); // retried request

    const response = await request("/auth/me");

    expect(response.status).toBe(200);
    expect(getAccessToken()).toBe("fresh");
    // The retried request must carry the refreshed token.
    expect(fetch.mock.calls[2][1].headers.Authorization).toBe("Bearer fresh");
  });

  it("clears tokens and emits auth:unauthorized when refresh fails", async () => {
    setTokens("stale", "refresh-1");
    fetch
      .mockResolvedValueOnce(res({ ok: false, status: 401 })) // original request
      .mockResolvedValueOnce(res({ ok: false, status: 401 })); // refresh fails

    const handler = vi.fn();
    window.addEventListener("auth:unauthorized", handler);

    const response = await request("/auth/me");

    expect(response.status).toBe(401);
    expect(getAccessToken()).toBeNull();
    expect(handler).toHaveBeenCalledTimes(1);
    window.removeEventListener("auth:unauthorized", handler);
  });
});

describe("deleteAccount", () => {
  it("clears tokens and returns true on success", async () => {
    setTokens("a", "r");
    fetch.mockResolvedValueOnce(res({ status: 200 }));

    const ok = await deleteAccount();

    expect(ok).toBe(true);
    expect(getAccessToken()).toBeNull();
    expect(fetch.mock.calls[0][1].method).toBe("DELETE");
  });

  it("returns false and keeps tokens when the request fails", async () => {
    setTokens("a", "r");
    fetch.mockResolvedValueOnce(res({ ok: false, status: 500 }));

    const ok = await deleteAccount();

    expect(ok).toBe(false);
    expect(getAccessToken()).toBe("a");
  });
});

describe("request timeout", () => {
  it("aborts and rejects with a friendly message when the backend never responds", async () => {
    vi.useFakeTimers();
    // Simulate a hung backend: the fetch only settles if its signal aborts.
    fetch.mockImplementation((_url, opts) =>
      new Promise((_resolve, reject) => {
        opts.signal.addEventListener("abort", () => {
          const err = new Error("aborted");
          err.name = "AbortError";
          reject(err);
        });
      })
    );

    const assertion = expect(login("u@example.com", "pw")).rejects.toThrow("Request timed out");
    await vi.advanceTimersByTimeAsync(30000);
    await assertion;

    vi.useRealTimers();
  });

  it("clears its abort timer when a response arrives in time", async () => {
    // Spy on the real clearTimeout: a successful response must cancel the
    // pending abort so it can never fire late and kill a later request.
    const clearSpy = vi.spyOn(globalThis, "clearTimeout");
    fetch.mockResolvedValueOnce(res({ body: { access_token: "a", refresh_token: "r" } }));

    await login("u@example.com", "pw");

    expect(clearSpy).toHaveBeenCalled();
    clearSpy.mockRestore();
  });

  it("still aborts the underlying fetch when the caller passes its own signal", async () => {
    // Regression: fetchWithTimeout used to build `{...options, signal: controller.signal}`,
    // which silently discarded any signal the caller passed in — a caller-initiated abort
    // (e.g. component unmount, user cancel) had no effect on the real network request.
    fetch.mockImplementation((_url, opts) => new Promise((_resolve, reject) => {
      opts.signal.addEventListener("abort", () => {
        const err = new Error("aborted");
        err.name = "AbortError";
        reject(err);
      });
    }));

    const controller = new AbortController();
    const promise = request("/auth/me", { signal: controller.signal });
    controller.abort();

    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
  });

  it("honors a custom timeoutMs instead of the 30s auth default", async () => {
    vi.useFakeTimers();
    fetch.mockImplementation((_url, opts) => new Promise((_resolve, reject) => {
      opts.signal.addEventListener("abort", () => {
        const err = new Error("aborted");
        err.name = "AbortError";
        reject(err);
      });
    }));

    const onReject = vi.fn();
    // Attach the handler in the same tick the promise is created, so it's
    // never briefly "unhandled" while fake timers advance.
    request("/align", { timeoutMs: 120000 }).catch(onReject);

    await vi.advanceTimersByTimeAsync(30000);
    expect(onReject).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(90000);
    expect(onReject).toHaveBeenCalledTimes(1);
    expect(onReject.mock.calls[0][0].message).toBe("Request timed out. Please try again.");

    vi.useRealTimers();
  });
});
