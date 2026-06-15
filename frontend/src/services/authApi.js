const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const TOKEN_KEY = "alignai_access_token";
const REFRESH_TOKEN_KEY = "alignai_refresh_token";

let refreshPromise = null;

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

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401 && options.retry !== false) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return request(endpoint, { ...options, retry: false });
    }
    clearTokens();
    window.location.href = "/login";
    throw new Error("Session expired");
  }

  return response;
}

async function refreshAccessToken() {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;

    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
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
  const response = await fetch(`${API_BASE_URL}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Signup failed" }));
    throw new Error(error.detail);
  }

  const data = await response.json();
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function login(email, password) {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Login failed" }));
    throw new Error(error.detail);
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

export { getAccessToken, getRefreshToken, setTokens, clearTokens, request };