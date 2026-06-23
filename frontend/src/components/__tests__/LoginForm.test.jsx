import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { mockLogin, mockNavigate } = vi.hoisted(() => ({
  mockLogin: vi.fn(),
  mockNavigate: vi.fn(),
}));

vi.mock("../../hooks/useAuth", () => ({ useAuth: () => ({ login: mockLogin }) }));
vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  Link: ({ children, to }) => <a href={to}>{children}</a>,
}));

import LoginForm from "../Auth/LoginForm";

beforeEach(() => {
  mockLogin.mockReset();
  mockNavigate.mockReset();
});

describe("LoginForm", () => {
  it("renders the email and password fields", () => {
    render(<LoginForm />);
    expect(screen.getByRole("heading", { name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("submits credentials and navigates home on success", async () => {
    mockLogin.mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(<LoginForm />);
    await user.type(screen.getByLabelText(/email/i), "u@example.com");
    await user.type(screen.getByLabelText(/password/i), "Password123!");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(mockLogin).toHaveBeenCalledWith("u@example.com", "Password123!");
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/"));
  });

  it("shows the error message and does not navigate on failure", async () => {
    mockLogin.mockRejectedValue(new Error("Invalid email or password"));
    const user = userEvent.setup();

    render(<LoginForm />);
    await user.type(screen.getByLabelText(/email/i), "u@example.com");
    await user.type(screen.getByLabelText(/password/i), "wrong");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText("Invalid email or password")).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("disables the button and shows a pending label while submitting", async () => {
    let resolveLogin;
    mockLogin.mockReturnValue(new Promise((resolve) => { resolveLogin = resolve; }));
    const user = userEvent.setup();

    render(<LoginForm />);
    await user.type(screen.getByLabelText(/email/i), "u@example.com");
    await user.type(screen.getByLabelText(/password/i), "Password123!");
    await user.click(screen.getByRole("button"));

    const button = screen.getByRole("button");
    await waitFor(() => expect(button).toBeDisabled());
    expect(button).toHaveTextContent(/signing in/i);

    resolveLogin();
    await waitFor(() => expect(mockNavigate).toHaveBeenCalled());
  });
});
