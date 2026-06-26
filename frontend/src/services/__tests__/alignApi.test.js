import { describe, it, expect, beforeEach, vi } from "vitest";
import { postAlign, extractErrorMessage } from "../alignApi";
import { setTokens } from "../authApi";

function res({ ok = true, status = 200 } = {}) {
  return { ok, status, body: "sse-stream" };
}

beforeEach(() => {
  localStorage.clear();
  global.fetch = vi.fn();
});

describe("postAlign", () => {
  it("posts session_id and user_message to /align, honoring the caller's abort signal", async () => {
    setTokens("token-1", "refresh-1");
    fetch.mockResolvedValueOnce(res());
    const controller = new AbortController();

    await postAlign({ sessionId: "sess-1", featureText: "Audit this feature", signal: controller.signal });

    const [url, opts] = fetch.mock.calls[0];
    expect(url).toContain("/align");
    expect(opts.method).toBe("POST");
    expect(opts.signal.aborted).toBe(false);
    controller.abort();
    expect(opts.signal.aborted).toBe(true);
    expect(JSON.parse(opts.body)).toEqual({
      session_id: "sess-1",
      user_message: "Audit this feature",
    });
    expect(opts.headers.Authorization).toBe("Bearer token-1");
  });

  it("returns the raw response so the caller can read the SSE body or inspect status", async () => {
    fetch.mockResolvedValueOnce(res({ ok: false, status: 429 }));

    const response = await postAlign({ sessionId: "sess-1", featureText: "x" });

    expect(response.ok).toBe(false);
    expect(response.status).toBe(429);
  });
});

describe("extractErrorMessage re-export", () => {
  it("is the same normalization helper authApi uses for HTTPException detail", () => {
    expect(extractErrorMessage("Rate limit exceeded", "fallback")).toBe("Rate limit exceeded");
    expect(extractErrorMessage(undefined, "fallback")).toBe("fallback");
  });
});
