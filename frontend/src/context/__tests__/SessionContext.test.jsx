import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { mockUseAuth } = vi.hoisted(() => ({ mockUseAuth: vi.fn() }));

vi.mock("../../services/authApi", () => ({ request: vi.fn() }));
vi.mock("../../hooks/useAuth", () => ({ useAuth: mockUseAuth }));

import * as authApi from "../../services/authApi";
import { SessionProvider, useSessionContext } from "../SessionContext";

function Consumer() {
  const {
    sessionId,
    sessions,
    isLoading,
    createSession,
    clearSession,
    deleteSession,
    setActiveSession,
    updateSessionTitle,
  } = useSessionContext();

  return (
    <div>
      <span data-testid="status">{isLoading ? "loading" : "ready"}</span>
      <span data-testid="sessionId">{sessionId ?? "none"}</span>
      <ul>
        {sessions.map((s) => (
          <li key={s.id}>{s.title || s.id}</li>
        ))}
      </ul>
      <button onClick={createSession}>create</button>
      <button onClick={clearSession}>clear</button>
      <button onClick={() => deleteSession("s1")}>delete-s1</button>
      <button onClick={() => setActiveSession("s2")}>activate-s2</button>
      <button onClick={() => updateSessionTitle("s1", "renamed")}>rename-s1</button>
    </div>
  );
}

function renderProvider() {
  return render(
    <SessionProvider>
      <Consumer />
    </SessionProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe("useSessionContext", () => {
  it("throws when used outside a SessionProvider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Consumer />)).toThrow(
      "useSessionContext must be used within a SessionProvider"
    );
    spy.mockRestore();
  });
});

describe("SessionProvider mount", () => {
  it("does not fetch sessions when the user is not authenticated", async () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false });
    renderProvider();
    expect(authApi.request).not.toHaveBeenCalled();
    expect(screen.getByTestId("sessionId")).toHaveTextContent("none");
  });

  it("fetches sessions once authenticated and selects the first as active", async () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true });
    authApi.request.mockResolvedValue({
      ok: true,
      json: async () => ({ sessions: [{ id: "s1", title: "First" }, { id: "s2", title: "Second" }] }),
    });

    renderProvider();

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(authApi.request).toHaveBeenCalledWith("/sessions");
    expect(screen.getByTestId("sessionId")).toHaveTextContent("s1");
    expect(screen.getByText("First")).toBeInTheDocument();
    expect(localStorage.getItem("alignai_active_session_id")).toBe("s1");
  });

  it("keeps the previously active session if it's still in the fetched list", async () => {
    localStorage.setItem("alignai_active_session_id", "s2");
    mockUseAuth.mockReturnValue({ isAuthenticated: true });
    authApi.request.mockResolvedValue({
      ok: true,
      json: async () => ({ sessions: [{ id: "s1", title: "First" }, { id: "s2", title: "Second" }] }),
    });

    renderProvider();

    await waitFor(() => expect(screen.getByTestId("sessionId")).toHaveTextContent("s2"));
  });
});

describe("SessionProvider actions", () => {
  beforeEach(() => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true });
    authApi.request.mockResolvedValue({
      ok: true,
      json: async () => ({ sessions: [{ id: "s1", title: "First" }] }),
    });
  });

  it("createSession() adds and activates a new session", async () => {
    const user = userEvent.setup();
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("sessionId")).toHaveTextContent("s1"));

    authApi.request.mockResolvedValueOnce({ ok: true, json: async () => ({ id: "s3", title: "New" }) });
    await user.click(screen.getByText("create"));

    await waitFor(() => expect(screen.getByTestId("sessionId")).toHaveTextContent("s3"));
    expect(screen.getByText("New")).toBeInTheDocument();
    expect(localStorage.getItem("alignai_active_session_id")).toBe("s3");
  });

  it("clearSession() deactivates the current session", async () => {
    const user = userEvent.setup();
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("sessionId")).toHaveTextContent("s1"));

    await user.click(screen.getByText("clear"));

    expect(screen.getByTestId("sessionId")).toHaveTextContent("none");
    expect(localStorage.getItem("alignai_active_session_id")).toBeNull();
  });

  it("setActiveSession() switches the active session and persists it", async () => {
    const user = userEvent.setup();
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("sessionId")).toHaveTextContent("s1"));

    await user.click(screen.getByText("activate-s2"));

    expect(screen.getByTestId("sessionId")).toHaveTextContent("s2");
    expect(localStorage.getItem("alignai_active_session_id")).toBe("s2");
  });

  it("deleteSession() removes the session and falls back to another when it was active", async () => {
    authApi.request.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ sessions: [{ id: "s1", title: "First" }, { id: "s2", title: "Second" }] }),
    });
    const user = userEvent.setup();
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("sessionId")).toHaveTextContent("s1"));

    authApi.request.mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    await user.click(screen.getByText("delete-s1"));

    await waitFor(() => expect(screen.getByTestId("sessionId")).toHaveTextContent("s2"));
    expect(screen.queryByText("First")).not.toBeInTheDocument();
  });

  it("updateSessionTitle() renames a session in place", async () => {
    const user = userEvent.setup();
    renderProvider();
    await waitFor(() => expect(screen.getByText("First")).toBeInTheDocument());

    authApi.request.mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    await user.click(screen.getByText("rename-s1"));

    expect(await screen.findByText("renamed")).toBeInTheDocument();
  });

  it("clears sessions when the user becomes unauthenticated", async () => {
    const { rerender } = renderProvider();
    await waitFor(() => expect(screen.getByTestId("sessionId")).toHaveTextContent("s1"));

    mockUseAuth.mockReturnValue({ isAuthenticated: false });
    rerender(
      <SessionProvider>
        <Consumer />
      </SessionProvider>
    );

    await waitFor(() => expect(screen.getByTestId("sessionId")).toHaveTextContent("none"));
  });
});
