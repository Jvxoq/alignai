import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AlignPage from "../AlignPage";
import { useSession } from "../../hooks/useSession";
import { postAlign } from "../../services/alignApi";

vi.mock("../../hooks/useSession");
vi.mock("../../services/alignApi");

function mockSession(overrides = {}) {
  useSession.mockReturnValue({
    sessionId: null,
    createSession: vi.fn(),
    updateSessionTitle: vi.fn(),
    fetchMessages: vi.fn().mockResolvedValue([]),
    ...overrides,
  });
}

function sseStream(lines) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      lines.forEach((line) => controller.enqueue(encoder.encode(line)));
      controller.close();
    },
  });
  return new Response(stream, { headers: { "Content-Type": "text/event-stream" } });
}

function sse(type, fields = {}) {
  return `data: ${JSON.stringify({ type, ...fields })}\n\n`;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AlignPage — initial render", () => {
  it("renders the empty state with the full intro header", () => {
    mockSession();
    render(<AlignPage />);
    expect(screen.getByText("AlignAI")).toBeInTheDocument();
    expect(screen.getByText(/Feature alignment auditing/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Audit for Compliance/i })).toBeDisabled();
  });

  it("enables the submit button once text is entered", async () => {
    mockSession();
    render(<AlignPage />);
    const textarea = screen.getByPlaceholderText(/Describe your feature/i);
    await userEvent.type(textarea, "Collects location in background");
    expect(screen.getByRole("button", { name: /Audit for Compliance/i })).toBeEnabled();
  });
});

describe("AlignPage — loading an existing session", () => {
  it("fetches and renders prior messages, inferring report vs chat from content", async () => {
    mockSession({
      sessionId: "sess-1",
      fetchMessages: vi.fn().mockResolvedValue([
        { role: "user", content: "What about Article 9?" },
        { role: "assistant", content: "# Compliance Report\n\nDetails here." },
      ]),
    });

    render(<AlignPage />);

    expect(await screen.findByText("What about Article 9?")).toBeInTheDocument();
    expect(await screen.findByText("Details here.")).toBeInTheDocument();
  });
});

describe("AlignPage — submitting with an existing session", () => {
  it("streams tokens and appends the final report as a message", async () => {
    mockSession({ sessionId: "sess-1" });
    postAlign.mockResolvedValue(
      sseStream([
        sse("start", { response_type: "report" }),
        sse("status", { message: "Retrieving documents..." }),
        sse("token", { data: "# Compliance Report\n" }),
        sse("token", { data: "Looks fine." }),
        sse("done"),
      ])
    );

    render(<AlignPage />);
    const textarea = screen.getByPlaceholderText(/Describe your feature/i);
    await userEvent.type(textarea, "Collects gyroscope data in background");
    await userEvent.click(screen.getByRole("button", { name: /Audit for Compliance/i }));

    expect(await screen.findByText("Collects gyroscope data in background")).toBeInTheDocument();

    await waitFor(() => {
      expect(postAlign).toHaveBeenCalledWith({
        sessionId: "sess-1",
        featureText: "Collects gyroscope data in background",
        signal: expect.any(AbortSignal),
      });
    });

    await waitFor(() => {
      expect(screen.getByText(/Looks fine\./)).toBeInTheDocument();
    });

    // The textarea clears immediately on submit, regardless of stream outcome.
    expect(textarea).toHaveValue("");
  });

  it("submits on Enter but not Shift+Enter", async () => {
    mockSession({ sessionId: "sess-1" });
    postAlign.mockResolvedValue(sseStream([sse("start", { response_type: "chat" }), sse("done")]));

    render(<AlignPage />);
    const textarea = screen.getByPlaceholderText(/Describe your feature/i);

    await userEvent.type(textarea, "hello{Shift>}{Enter}{/Shift}");
    expect(postAlign).not.toHaveBeenCalled();

    await userEvent.type(textarea, "{Enter}");
    await waitFor(() => expect(postAlign).toHaveBeenCalledTimes(1));
  });
});

describe("AlignPage — creating a session on first message", () => {
  it("creates a session, does not re-fetch (and clobber) the optimistic message, then streams", async () => {
    const createSession = vi.fn().mockResolvedValue("new-sess");
    const fetchMessages = vi.fn().mockResolvedValue([]);
    mockSession({ sessionId: null, createSession, fetchMessages });
    postAlign.mockResolvedValue(sseStream([sse("start", { response_type: "chat" }), sse("done")]));

    const { rerender } = render(<AlignPage />);
    const textarea = screen.getByPlaceholderText(/Describe your feature/i);
    await userEvent.type(textarea, "First message ever");
    await userEvent.click(screen.getByRole("button", { name: /Audit for Compliance/i }));

    expect(await screen.findByText("First message ever")).toBeInTheDocument();
    await waitFor(() => expect(createSession).toHaveBeenCalledTimes(1));

    // Simulate the session context now reporting the new id (as the real
    // SessionProvider would once createSession's setState lands).
    mockSession({ sessionId: "new-sess", createSession, fetchMessages });
    rerender(<AlignPage />);

    await waitFor(() => expect(postAlign).toHaveBeenCalledWith(
      expect.objectContaining({ sessionId: "new-sess" })
    ));

    // Regression: fetchMessages must not be called for the session-creation
    // transition — it would resolve to [] (no LangGraph thread yet) and wipe
    // the optimistic "First message ever" bubble.
    expect(fetchMessages).not.toHaveBeenCalled();
    expect(screen.getByText("First message ever")).toBeInTheDocument();
  });

  it("does not fire a second createSession when submitted again before the first resolves", async () => {
    let resolveCreate;
    const createSession = vi.fn(() => new Promise((resolve) => { resolveCreate = resolve; }));
    mockSession({ sessionId: null, createSession });
    postAlign.mockResolvedValue(sseStream([sse("done")]));

    render(<AlignPage />);
    const textarea = screen.getByPlaceholderText(/Describe your feature/i);
    const button = screen.getByRole("button", { name: /Audit for Compliance/i });

    await userEvent.type(textarea, "First");
    await userEvent.click(button);
    expect(createSession).toHaveBeenCalledTimes(1);

    // Button should now be in its loading state, blocking a second submit
    // before createSession's promise has resolved.
    await waitFor(() => expect(button).toBeDisabled());
    resolveCreate("new-sess");
  });
});

describe("AlignPage — error handling", () => {
  it("shows a single error and rolls back the optimistic message when session creation fails", async () => {
    mockSession({ sessionId: null, createSession: vi.fn().mockResolvedValue(null) });

    render(<AlignPage />);
    const textarea = screen.getByPlaceholderText(/Describe your feature/i);
    await userEvent.type(textarea, "Will fail to create a session");
    await userEvent.click(screen.getByRole("button", { name: /Audit for Compliance/i }));

    expect(await screen.findByText(/Could not create a new session/i)).toBeInTheDocument();
    expect(screen.queryByText("Will fail to create a session")).not.toBeInTheDocument();

    // Regression: this error path must render exactly once, not duplicated
    // between the inline status block and the standalone ErrorDisplay.
    expect(screen.getAllByText(/Could not create a new session/i)).toHaveLength(1);
    expect(postAlign).not.toHaveBeenCalled();
  });

  it("shows exactly one error indicator when the stream fails before any tokens arrive", async () => {
    mockSession({ sessionId: "sess-1" });
    postAlign.mockResolvedValue(
      sseStream([sse("error", { code: 500, message: "Server error" })])
    );

    render(<AlignPage />);
    const textarea = screen.getByPlaceholderText(/Describe your feature/i);
    await userEvent.type(textarea, "Trigger a server error");
    await userEvent.click(screen.getByRole("button", { name: /Audit for Compliance/i }));

    expect(await screen.findByText("Server error")).toBeInTheDocument();
    expect(screen.getAllByText("Server error")).toHaveLength(1);
  });

  it("shows exactly one error indicator when the stream fails after partial tokens", async () => {
    mockSession({ sessionId: "sess-1" });
    postAlign.mockResolvedValue(
      sseStream([
        sse("start", { response_type: "chat" }),
        sse("token", { data: "Partial answer..." }),
        sse("error", { code: 500, message: "Server error mid-stream" }),
      ])
    );

    render(<AlignPage />);
    const textarea = screen.getByPlaceholderText(/Describe your feature/i);
    await userEvent.type(textarea, "Trigger a mid-stream error");
    await userEvent.click(screen.getByRole("button", { name: /Audit for Compliance/i }));

    expect(await screen.findByText("Server error mid-stream")).toBeInTheDocument();
    expect(screen.getAllByText("Server error mid-stream")).toHaveLength(1);
  });
});
