import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { mockDeleteAccount, mockNavigate } = vi.hoisted(() => ({
  mockDeleteAccount: vi.fn(),
  mockNavigate: vi.fn(),
}));

vi.mock("../../hooks/useAuth", () => ({ useAuth: () => ({ deleteAccount: mockDeleteAccount }) }));
vi.mock("react-router-dom", () => ({ useNavigate: () => mockNavigate }));

import DeleteAccountModal from "../Auth/DeleteAccountModal";

beforeEach(() => {
  mockDeleteAccount.mockReset();
  mockNavigate.mockReset();
});

describe("DeleteAccountModal", () => {
  it("renders nothing when closed", () => {
    const { container } = render(<DeleteAccountModal isOpen={false} onClose={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the confirmation dialog when open", () => {
    render(<DeleteAccountModal isOpen onClose={vi.fn()} />);
    expect(screen.getByRole("heading", { name: /delete account/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^delete account$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
  });

  it("calls onClose when Cancel is clicked", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<DeleteAccountModal isOpen onClose={onClose} />);
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it("navigates to /signup and closes on successful deletion", async () => {
    mockDeleteAccount.mockResolvedValue(true);
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<DeleteAccountModal isOpen onClose={onClose} />);

    await user.click(screen.getByRole("button", { name: /^delete account$/i }));

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/signup"));
    expect(onClose).toHaveBeenCalled();
  });

  it("shows an error and stays open when deletion reports failure", async () => {
    mockDeleteAccount.mockResolvedValue(false);
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<DeleteAccountModal isOpen onClose={onClose} />);

    await user.click(screen.getByRole("button", { name: /^delete account$/i }));

    expect(await screen.findByText(/failed to delete account/i)).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("shows the thrown error message when deletion rejects", async () => {
    mockDeleteAccount.mockRejectedValue(new Error("Network error"));
    const user = userEvent.setup();
    render(<DeleteAccountModal isOpen onClose={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /^delete account$/i }));

    expect(await screen.findByText("Network error")).toBeInTheDocument();
  });
});
