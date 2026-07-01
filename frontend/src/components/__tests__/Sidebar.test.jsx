import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { mockUseAuth, mockUseSession, mockNavigate } = vi.hoisted(() => ({
  mockUseAuth: vi.fn(),
  mockUseSession: vi.fn(),
  mockNavigate: vi.fn(),
}));

vi.mock("../../hooks/useAuth", () => ({ useAuth: mockUseAuth }));
vi.mock("../../hooks/useSession", () => ({ useSession: mockUseSession }));
vi.mock("react-router-dom", () => ({ useNavigate: () => mockNavigate }));
vi.mock("../Auth/DeleteAccountModal", () => ({
  default: ({ isOpen }) => (isOpen ? <div>delete-account-modal</div> : null),
}));

import Sidebar from "../Layout/Sidebar";

const baseSession = {
  sessionId: null,
  sessions: [],
  isLoading: false,
  createSession: vi.fn(),
  clearSession: vi.fn(),
  deleteSession: vi.fn(),
  setActiveSession: vi.fn(),
};

beforeEach(() => {
  vi.clearAllMocks();
  mockUseAuth.mockReturnValue({ logout: vi.fn() });
  mockUseSession.mockReturnValue({ ...baseSession });
});

describe("Sidebar", () => {
  it("shows a loading state while sessions are loading", () => {
    mockUseSession.mockReturnValue({ ...baseSession, isLoading: true });
    render(<Sidebar />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows an empty state with a call to action when there are no sessions", () => {
    render(<Sidebar />);
    expect(screen.getByText(/no sessions yet/i)).toBeInTheDocument();
    expect(screen.getByText(/create your first session/i)).toBeInTheDocument();
  });

  it("lists sessions and marks the active one", () => {
    mockUseSession.mockReturnValue({
      ...baseSession,
      sessionId: "s1",
      sessions: [{ id: "s1", title: "First" }, { id: "s2", title: "Second" }],
    });
    render(<Sidebar />);
    expect(screen.getByText("First")).toBeInTheDocument();
    expect(screen.getByText("Second")).toBeInTheDocument();
  });

  it("calls createSession when clicking the empty-state CTA", async () => {
    const createSession = vi.fn();
    mockUseSession.mockReturnValue({ ...baseSession, createSession });
    const user = userEvent.setup();
    render(<Sidebar />);
    await user.click(screen.getByText(/create your first session/i));
    expect(createSession).toHaveBeenCalled();
  });

  it("calls clearSession when clicking + New Session", async () => {
    const clearSession = vi.fn();
    mockUseSession.mockReturnValue({
      ...baseSession,
      sessions: [{ id: "s1", title: "First" }],
      clearSession,
    });
    const user = userEvent.setup();
    render(<Sidebar />);
    await user.click(screen.getByText(/new session/i));
    expect(clearSession).toHaveBeenCalled();
  });

  it("activates a session when its name is clicked", async () => {
    const setActiveSession = vi.fn();
    mockUseSession.mockReturnValue({
      ...baseSession,
      sessions: [{ id: "s1", title: "First" }],
      setActiveSession,
    });
    const user = userEvent.setup();
    render(<Sidebar />);
    await user.click(screen.getByText("First"));
    expect(setActiveSession).toHaveBeenCalledWith("s1");
  });

  it("confirms before deleting a session, then deletes on confirm", async () => {
    const deleteSession = vi.fn().mockResolvedValue(true);
    mockUseSession.mockReturnValue({
      ...baseSession,
      sessions: [{ id: "s1", title: "First" }],
      deleteSession,
    });
    const user = userEvent.setup();
    render(<Sidebar />);

    await user.click(screen.getByLabelText(/delete session/i));
    expect(screen.getByText(/are you sure you want to delete this session/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(deleteSession).toHaveBeenCalledWith("s1");
  });

  it("calls deleteSession and closes the confirmation modal even when deletion fails", async () => {
    const deleteSession = vi.fn().mockResolvedValue(false);
    mockUseSession.mockReturnValue({
      ...baseSession,
      sessions: [{ id: "s1", title: "First" }],
      deleteSession,
    });
    const user = userEvent.setup();
    render(<Sidebar />);

    await user.click(screen.getByLabelText(/delete session/i));
    await user.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(deleteSession).toHaveBeenCalledWith("s1"));
    expect(screen.queryByText(/are you sure you want to delete this session/i)).not.toBeInTheDocument();
  });

  it("logs out and navigates to /login on Sign Out", async () => {
    const logout = vi.fn().mockResolvedValue(undefined);
    mockUseAuth.mockReturnValue({ logout });
    const user = userEvent.setup();
    render(<Sidebar />);

    await user.click(screen.getByText(/sign out/i));

    expect(logout).toHaveBeenCalled();
    expect(mockNavigate).toHaveBeenCalledWith("/login");
  });

  it("opens the delete-account modal", async () => {
    const user = userEvent.setup();
    render(<Sidebar />);
    await user.click(screen.getByText(/delete account/i));
    expect(screen.getByText("delete-account-modal")).toBeInTheDocument();
  });
});
