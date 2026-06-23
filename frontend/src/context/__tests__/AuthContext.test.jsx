import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../../services/authApi", () => ({
  login: vi.fn(),
  signup: vi.fn(),
  logout: vi.fn(),
  deleteAccount: vi.fn(),
  request: vi.fn(),
  getAccessToken: vi.fn(),
}));

import * as authApi from "../../services/authApi";
import { AuthProvider, useAuth } from "../AuthContext";

function Consumer() {
  const { isAuthenticated, isLoading, user, login, signup, logout, deleteAccount } = useAuth();
  return (
    <div>
      <span data-testid="status">
        {isLoading ? "loading" : isAuthenticated ? "authenticated" : "anonymous"}
      </span>
      <span data-testid="email">{user?.email ?? "no-user"}</span>
      <button onClick={() => login("u@example.com", "pw")}>login</button>
      <button onClick={() => signup("u@example.com", "pw")}>signup</button>
      <button onClick={() => logout()}>logout</button>
      <button onClick={() => deleteAccount()}>delete</button>
    </div>
  );
}

function renderProvider() {
  return render(
    <AuthProvider>
      <Consumer />
    </AuthProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useAuth", () => {
  it("throws when used outside an AuthProvider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Consumer />)).toThrow("useAuth must be used within an AuthProvider");
    spy.mockRestore();
  });
});

describe("AuthProvider mount / checkAuth", () => {
  it("resolves to anonymous when no token is stored", async () => {
    authApi.getAccessToken.mockReturnValue(null);
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
    expect(authApi.request).not.toHaveBeenCalled();
  });

  it("loads the user from /auth/me when a token exists", async () => {
    authApi.getAccessToken.mockReturnValue("token");
    authApi.request.mockResolvedValue({ ok: true, json: async () => ({ email: "me@example.com" }) });

    renderProvider();

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
    expect(screen.getByTestId("email")).toHaveTextContent("me@example.com");
    expect(authApi.request).toHaveBeenCalledWith("/auth/me");
  });

  it("stays anonymous when /auth/me is not ok", async () => {
    authApi.getAccessToken.mockReturnValue("token");
    authApi.request.mockResolvedValue({ ok: false });
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
  });
});

describe("AuthProvider actions", () => {
  beforeEach(() => {
    authApi.getAccessToken.mockReturnValue(null);
  });

  it("login() calls the API and flips to authenticated", async () => {
    authApi.login.mockResolvedValue({ access_token: "a", refresh_token: "r" });
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));

    await userEvent.click(screen.getByText("login"));

    expect(authApi.login).toHaveBeenCalledWith("u@example.com", "pw");
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
  });

  it("signup() calls the API and flips to authenticated", async () => {
    authApi.signup.mockResolvedValue({ access_token: "a", refresh_token: "r" });
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));

    await userEvent.click(screen.getByText("signup"));

    expect(authApi.signup).toHaveBeenCalledWith("u@example.com", "pw");
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
  });

  it("logout() clears authentication state", async () => {
    authApi.getAccessToken.mockReturnValue("token");
    authApi.request.mockResolvedValue({ ok: true, json: async () => ({ email: "me@example.com" }) });
    authApi.logout.mockResolvedValue(undefined);
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));

    await userEvent.click(screen.getByText("logout"));

    expect(authApi.logout).toHaveBeenCalled();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
    expect(screen.getByTestId("email")).toHaveTextContent("no-user");
  });

  it("deleteAccount() clears state only when the API reports success", async () => {
    authApi.deleteAccount.mockResolvedValueOnce(false);
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));

    // Make it look authenticated first via a successful login.
    authApi.login.mockResolvedValue({});
    await userEvent.click(screen.getByText("login"));
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));

    // Failed delete must NOT log the user out.
    await userEvent.click(screen.getByText("delete"));
    await waitFor(() => expect(authApi.deleteAccount).toHaveBeenCalled());
    expect(screen.getByTestId("status")).toHaveTextContent("authenticated");

    // Successful delete clears state.
    authApi.deleteAccount.mockResolvedValueOnce(true);
    await userEvent.click(screen.getByText("delete"));
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
  });

  it("responds to a global auth:unauthorized event by de-authenticating", async () => {
    authApi.getAccessToken.mockReturnValue("token");
    authApi.request.mockResolvedValue({ ok: true, json: async () => ({ email: "me@example.com" }) });
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));

    window.dispatchEvent(new Event("auth:unauthorized"));

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
  });
});
