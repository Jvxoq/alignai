import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { mockSignup, mockNavigate } = vi.hoisted(() => ({
  mockSignup: vi.fn(),
  mockNavigate: vi.fn(),
}));

vi.mock("../../hooks/useAuth", () => ({ useAuth: () => ({ signup: mockSignup }) }));
vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  Link: ({ children, to }) => <a href={to}>{children}</a>,
}));

import SignupForm from "../Auth/SignupForm";

beforeEach(() => {
  mockSignup.mockReset();
  mockNavigate.mockReset();
});

async function fill(user, { email = "u@example.com", password, confirm }) {
  if (email) await user.type(screen.getByLabelText(/^email$/i), email);
  if (password) await user.type(screen.getByLabelText(/^password$/i), password);
  if (confirm) await user.type(screen.getByLabelText(/confirm password/i), confirm);
}

describe("SignupForm", () => {
  it("renders all three fields", () => {
    render(<SignupForm />);
    expect(screen.getByRole("heading", { name: /create account/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
  });

  it("blocks submission when passwords do not match", async () => {
    const user = userEvent.setup();
    render(<SignupForm />);
    await fill(user, { password: "Password123!", confirm: "Different123!" });
    await user.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByText("Passwords do not match")).toBeInTheDocument();
    expect(mockSignup).not.toHaveBeenCalled();
  });

  it("blocks submission when the password is too short", async () => {
    const user = userEvent.setup();
    render(<SignupForm />);
    await fill(user, { password: "short", confirm: "short" });
    await user.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByText("Password must be at least 8 characters")).toBeInTheDocument();
    expect(mockSignup).not.toHaveBeenCalled();
  });

  it("submits and navigates home on success", async () => {
    mockSignup.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<SignupForm />);
    await fill(user, { password: "Password123!", confirm: "Password123!" });
    await user.click(screen.getByRole("button", { name: /create account/i }));

    expect(mockSignup).toHaveBeenCalledWith("u@example.com", "Password123!");
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/"));
  });

  it("surfaces a server-side error and does not navigate", async () => {
    mockSignup.mockRejectedValue(new Error("Email already registered"));
    const user = userEvent.setup();
    render(<SignupForm />);
    await fill(user, { password: "Password123!", confirm: "Password123!" });
    await user.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByText("Email already registered")).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
