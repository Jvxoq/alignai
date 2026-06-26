const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const TOKEN_KEY = "alignai_access_token";
const REFRESH_TOKEN_KEY = "alignai_refresh_token";

// Hard ceiling on every auth request. Without it, a slow or unreachable backend
// leaves fetch pending forever — the form's submit button stays disabled with no
// error and the user is stuck. AbortController turns that into a clear failure.
const REQUEST_TIMEOUT_MS = 30000;

let refreshPromise = null;

async function fetchWithTimeout(url, options = {}) {
  const { timeoutMs = REQUEST_TIMEOUT_MS, signal: callerSignal, ...rest } = options;
  const timeoutController = new AbortController();
  const timeoutId = setTimeout(() => timeoutController.abort(), timeoutMs);
  // Respect both: the caller may abort (e.g. component unmount, user cancel)
  // independently of our own timeout ceiling — neither should silently
  // override the other.
  const signal = callerSignal
    ? AbortSignal.any([callerSignal, timeoutController.signal])
    : timeoutController.signal;

  try {
    return await fetch(url, { ...rest, signal });
  } catch (err) {
    if (err.name === "AbortError") {
      if (timeoutController.signal.aborted && !callerSignal?.aborted) {
        throw new Error("Request timed out. Please try again.");
      }
      throw err;
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

// FastAPI returns `detail` as a string for explicit HTTPExceptions (401/409/…)
// but as an array of `{loc, msg, type}` objects for 422 request-validation
// errors. Normalize both into a single human-readable message so the UI never
// renders "[object Object]".
function extractErrorMessage(detail, fallback) {
  if (typeof detail === "string" && detail) {
    return detail;
  }
  if (Array.isArray(detail)) {
    const message = detail
      .map((item) => item?.msg)
      .filter(Boolean)
      .join(", ");
    if (message) {
      return message;
    }
  }
  return fallback;
}

function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

function setTokens(accessToken, refreshToken) {
  localStorage.setItem(TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = { ...options.headers };

  if (options.body) {
    headers["Content-Type"] = "application/json";
  }

  const accessToken = getAccessToken();
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  const response = await fetchWithTimeout(url, {
    ...options,
    headers,
  });

  if (response.status === 401 && options.retry !== false) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return request(endpoint, { ...options, retry: false });
    }
    clearTokens();
    window.dispatchEvent(new Event("auth:unauthorized"));
  }

  return response;
}

async function refreshAccessToken() {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;

    try {
      const response = await fetchWithTimeout(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) return false;

      const data = await response.json();
      setTokens(data.access_token, data.refresh_token);
      return true;
    } catch {
      return false;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

export async function signup(email, password) {
  const response = await fetchWithTimeout(`${API_BASE_URL}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error.detail, "Signup failed"));
  }

  const data = await response.json();
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function login(email, password) {
  const response = await fetchWithTimeout(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractErrorMessage(error.detail, "Login failed"));
  }

  const data = await response.json();
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function logout() {
  clearTokens();
}

export async function deleteAccount() {
  const response = await request("/users/me", { method: "DELETE" });
  if (response && response.ok) {
    clearTokens();
    return true;
  }
  return false;
}

export { getAccessToken, getRefreshToken, setTokens, clearTokens, request, extractErrorMessage };