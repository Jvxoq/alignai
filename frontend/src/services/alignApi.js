import { request, extractErrorMessage } from "./authApi";

export { extractErrorMessage };

// The agent can run up to 3 retrieve/rewrite attempts plus LLM generation —
// well past the 30s default tuned for quick auth requests.
const ALIGN_TIMEOUT_MS = 120000;

export async function postAlign({ sessionId, featureText, signal }) {
  const response = await request("/align", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      user_message: featureText,
    }),
    signal,
    timeoutMs: ALIGN_TIMEOUT_MS,
  });
  return response;
}
