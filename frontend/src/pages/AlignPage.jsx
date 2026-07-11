import { useCallback, useEffect, useRef, useState } from "react";
import { ChatSkeleton } from "../components/ChatSkeleton";
import AuditButton from "../components/InputSection/AuditButton";
import CharacterCounter from "../components/InputSection/CharacterCounter";
import FeatureTextarea from "../components/InputSection/FeatureTextarea";
import ErrorDisplay from "../components/ResponseSection/ErrorDisplay";
import PlainTextDisplay from "../components/ResponseSection/PlainTextDisplay";
import ReportDocument from "../components/ResponseSection/ReportDocument";
import StatusIndicator from "../components/ResponseSection/StatusIndicator";
import { useSession } from "../hooks/useSession";
import { useStream } from "../hooks/useStream";
import { postAlign } from "../services/alignApi";

const MAX_LENGTH = 2000;
// Mirrors the backend's MAX_SESSIONS_PER_USER (app/core/config.py).
const MAX_SESSIONS = 3;

export default function AlignPage() {
  const [featureText, setFeatureText] = useState("");
  const [messages, setMessages] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const { sessionId, sessions, createSession, updateSessionTitle, fetchMessages } = useSession();
  const { status, responseType, statusMessage, tokens, error, startStream, abort, reset, setError, setStatus } = useStream();
  const messagesEndRef = useRef(null);
  const messagesRef = useRef(null);
  const hasSetTitle = useRef(false);
  const skipNextFetchRef = useRef(false);

  const isLoading = status === "connecting" || status === "streaming";
  const canSubmit = featureText.trim().length > 0 && !isLoading;
  // An active session (even an empty one, e.g. just-selected from the sidebar)
  // keeps the compact chat layout — only the "no session yet" state shows the
  // full hero screen. Otherwise finishing history-load on an empty session
  // would flip isCompact back to false and snap the layout back to the hero.
  const isCompact = messages.length > 0 || historyLoading || sessionId !== null;
  // No active session AND already at the cap → creating a new one would 409,
  // so hide the chatbox and show the limit message in its place.
  const limitReached = sessionId === null && sessions.length >= MAX_SESSIONS;

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  const handleAudit = async () => {
    const text = featureText.trim();
    if (!text || isLoading) return;

    setFeatureText("");
    reset();
    // Mark as loading immediately so a fast double-submit (e.g. typing new
    // text and hitting Enter again) can't fire a second createSession() call
    // while this one is still awaiting the network.
    setStatus("connecting");

    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: "user",
        content: text,
        responseType: null,
        timestamp: new Date(),
      },
    ]);

    let currentSessionId = sessionId;
    if (!currentSessionId) {
      currentSessionId = await createSession();
      if (currentSessionId === "LIMIT_REACHED") {
        // Safety net: count was stale (e.g. another tab). limitReached is
        // derived from `sessions`, which refreshes on the next fetch.
        setMessages((prev) => prev.slice(0, -1));
        return;
      }
      if (!currentSessionId) {
        setMessages((prev) => prev.slice(0, -1));
        setError("Could not create a new session. Please try again.");
        return;
      }
      // A freshly created session has no LangGraph thread yet, so the
      // session-switch effect's fetchMessages() would resolve to [] and wipe
      // out the optimistic user message above. Skip that one fetch — we
      // already know the local state is correct.
      skipNextFetchRef.current = true;
    }

    startStream((signal) =>
      postAlign({ sessionId: currentSessionId, featureText: text, signal })
    );
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSubmit) handleAudit();
    }
  };

  useEffect(() => {
    if (status === "complete" && tokens) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: tokens,
          responseType: responseType,
          timestamp: new Date(),
        },
      ]);
    }
  }, [status, tokens, responseType]);

  useEffect(() => {
    if (status === "error") {
      setMessages((prev) => {
        if (prev.length > 0 && prev[prev.length - 1].role === "user") {
          // Restore the failed prompt into the input instead of losing it --
          // the textarea was already cleared when the audit was submitted.
          setFeatureText(prev[prev.length - 1].content);
          return prev.slice(0, -1);
        }
        return prev;
      });
    }
  }, [status]);

  const prevSessionRef = useRef(sessionId);

  useEffect(() => {
    const prev = prevSessionRef.current;
    prevSessionRef.current = sessionId;

    if (sessionId === null || (prev !== null && prev !== sessionId)) {
      // Abort any stream still running for the session we're leaving so its
      // late tokens/done event can't land on the newly active session.
      abort();
      setMessages([]);
      setFeatureText("");
      hasSetTitle.current = false;
      reset();
    }

    if (sessionId === null) {
      setHistoryLoading(false);
    }

    if (sessionId !== null) {
      if (skipNextFetchRef.current) {
        skipNextFetchRef.current = false;
        return;
      }
      let cancelled = false;
      setHistoryLoading(true);
      fetchMessages(sessionId).then((fetched) => {
        if (cancelled) return;
        const mapped = fetched.map((m) => ({
          id: crypto.randomUUID(),
          role: m.role,
          content: m.content,
          responseType: m.role === "assistant"
            ? (m.content.startsWith("# Compliance") ? "report" : "chat")
            : null,
          timestamp: new Date(),
        }));
        setMessages(mapped);
        if (mapped.length > 0) hasSetTitle.current = true;
        setHistoryLoading(false);
      });
      return () => { cancelled = true; };
    }
  }, [sessionId, reset, fetchMessages, abort]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, status, scrollToBottom]);

  useEffect(() => {
    return () => abort();
  }, [abort]);

  useEffect(() => {
    if (messages.length === 1 && messages[0].role === "user" && sessionId && !hasSetTitle.current) {
      hasSetTitle.current = true;
      const title = messages[0].content.slice(0, 40) + (messages[0].content.length > 40 ? "..." : "");
      updateSessionTitle(sessionId, title);
    }
  }, [messages, sessionId, updateSessionTitle]);

  return (
    <div className={`app ${isCompact ? "app--chat" : ""}`}>
      <header className={`app-header ${isCompact ? "app-header--compact" : ""}`}>
        <h1>AlignAI</h1>
        {!isCompact && <p>Feature alignment auditing powered by AI</p>}
      </header>

      {limitReached ? (
        <main className="chat-layout">
          <div className="session-limit-message">
            You have reached maximum sessions.
          </div>
        </main>
      ) : (
      <main className="chat-layout">
        <div className="chat-messages" ref={messagesRef}>
          {historyLoading ? <ChatSkeleton /> : messages.map((msg) => (
            <div key={msg.id} className={`chat-message chat-message--${msg.role}`}>
              <div className="chat-message-content">
                {msg.role === "user" ? (
                  <div className="user-message">{msg.content}</div>
                ) : (
                  <>
                    {msg.responseType === "report" && <ReportDocument content={msg.content} />}
                    {msg.responseType && msg.responseType !== "report" && <PlainTextDisplay text={msg.content} />}
                  </>
                )}
              </div>
            </div>
          ))}

          {status === "streaming" && (
            <div className="chat-message chat-message--assistant">
              <StatusIndicator status={status} message={statusMessage} error={error} />
              {responseType === "report" && <ReportDocument content={tokens} />}
              {responseType && responseType !== "report" && <PlainTextDisplay text={tokens} />}
            </div>
          )}

          {/* A stream that errors out after producing partial content should
              still show that content -- the error itself is reported once,
              below, via ErrorDisplay. */}
          {status === "error" && tokens && (
            <div className="chat-message chat-message--assistant">
              {responseType === "report" && <ReportDocument content={tokens} />}
              {responseType && responseType !== "report" && <PlainTextDisplay text={tokens} />}
            </div>
          )}

          {status === "error" && !tokens && (
            <div className="chat-message chat-message--assistant">
              <StatusIndicator status={status} message={statusMessage} error={error} />
            </div>
          )}

          {/* The streaming/error block above already shows this error inline
              when there's no partial content; only show this one for the
              partial-content case (tokens present), to avoid a duplicate. */}
          {error && tokens && <ErrorDisplay error={error} />}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-container">
          <section className={`input-section ${isCompact ? "input-section--compact" : ""}`}>
            <FeatureTextarea
              value={featureText}
              onChange={setFeatureText}
              maxLength={MAX_LENGTH}
              disabled={isLoading}
              compact={isCompact}
              onKeyDown={handleKeyDown}
            />
            <div className="input-footer">
              <CharacterCounter current={featureText.length} max={MAX_LENGTH} />
              <AuditButton onClick={handleAudit} disabled={!canSubmit} loading={isLoading} compact={isCompact} />
            </div>
          </section>
        </div>
      </main>
      )}
    </div>
  );
}
