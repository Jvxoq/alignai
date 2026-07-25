import { fetchWithTimeout, extractErrorMessage } from "./authApi";

export { extractErrorMessage };

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// The agent can run up to 3 retrieve/rewrite attempts plus LLM generation --
// same generous ceiling as the authenticated align call.
const TRIAL_TIMEOUT_MS = 120000;

// Unlike every other call in this app, the trial endpoint has no Bearer token
// to authenticate with -- it's the one anonymous call site. It's gated by a
// signed cookie instead, so credentials must be included for that cookie to
// round-trip cross-site (frontend and backend live on different origins).
export async function postTrialAlign({ featureText, signal }) {
  const response = await fetchWithTimeout(`${API_BASE_URL}/trial/align`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ user_message: featureText }),
    signal,
    timeoutMs: TRIAL_TIMEOUT_MS,
  });
  return response;
}
