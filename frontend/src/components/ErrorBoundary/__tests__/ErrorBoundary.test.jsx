import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import ErrorBoundary from "../ErrorBoundary";

function Boom() {
  throw new Error("boom");
}

function Safe() {
  return <div>All good</div>;
}

describe("ErrorBoundary", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders children when nothing throws", () => {
    render(
      <MemoryRouter>
        <ErrorBoundary>
          <Safe />
        </ErrorBoundary>
      </MemoryRouter>
    );
    expect(screen.getByText("All good")).toBeInTheDocument();
  });

  it("catches a render error and shows the default fallback", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <MemoryRouter>
        <ErrorBoundary>
          <Boom />
        </ErrorBoundary>
      </MemoryRouter>
    );
    expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument();
  });

  // Regression: main.jsx used to wrap ErrorBoundary AROUND BrowserRouter, so
  // catching an error swapped in FallbackUI with no Router ancestor at all.
  // FallbackUI calls useNavigate(), which throws in that case — the safety
  // net itself crashed exactly when it was needed. The fix nests ErrorBoundary
  // *inside* the Router; this test pins that requirement down.
  it("renders the fallback without crashing when nested inside a Router (matches main.jsx wiring)", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() =>
      render(
        <MemoryRouter>
          <ErrorBoundary>
            <Boom />
          </ErrorBoundary>
        </MemoryRouter>
      )
    ).not.toThrow();
    expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument();
    expect(screen.getByText("Go Home")).toBeInTheDocument();
  });

  it("resets and re-renders children when 'Try Again' is clicked", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    let shouldThrow = true;
    function Flaky() {
      if (shouldThrow) throw new Error("boom");
      return <div>Recovered</div>;
    }

    render(
      <MemoryRouter>
        <ErrorBoundary>
          <Flaky />
        </ErrorBoundary>
      </MemoryRouter>
    );
    expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument();

    shouldThrow = false;
    fireEvent.click(screen.getByText("Try Again"));

    expect(screen.getByText("Recovered")).toBeInTheDocument();
  });

  it("navigates home and resets when 'Go Home' is clicked", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    // The deep route throws; "/" renders safely, so a successful navigate +
    // reset lands on real content instead of re-triggering the same error.
    render(
      <MemoryRouter initialEntries={["/some/deep/route"]}>
        <Routes>
          <Route path="/" element={<Safe />} />
          <Route
            path="/some/deep/route"
            element={
              <ErrorBoundary>
                <Boom />
              </ErrorBoundary>
            }
          />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument();

    expect(() => fireEvent.click(screen.getByText("Go Home"))).not.toThrow();

    expect(screen.queryByText(/Something went wrong/i)).not.toBeInTheDocument();
    expect(screen.getByText("All good")).toBeInTheDocument();
  });

  it("uses a custom fallback render prop when provided", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <MemoryRouter>
        <ErrorBoundary fallback={({ error, resetError }) => (
          <div>
            <span>Custom: {error.message}</span>
            <button onClick={resetError}>Reset</button>
          </div>
        )}>
          <Boom />
        </ErrorBoundary>
      </MemoryRouter>
    );
    expect(screen.getByText("Custom: boom")).toBeInTheDocument();
  });
});
