import { useCallback, useEffect, useRef, useState } from "react";
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

export default function AlignPage() {
  const [featureText, setFeatureText] = useState("");
  const [messages, setMessages] = useState([]);
  const { sessionId, createSession, updateSessionTitle, fetchMessages } = useSession();
  const { status, responseType, statusMessage, tokens, error, startStream, reset, setError } = useStream();
  const messagesEndRef = useRef(null);
  const messagesRef = useRef(null);
  const hasSetTitle = useRef(false);

  const isLoading = status === "connecting" || status === "streaming";
  const canSubmit = featureText.trim().length > 0 && !isLoading;
  const isCompact = messages.length > 0;

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  const handleAudit = async () => {
    const text = featureText.trim();
    if (!text) return;

    setFeatureText("");
    reset();

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
      if (!currentSessionId) {
        setMessages((prev) => prev.slice(0, -1));
        setError("Could not create a new session. Please try again.");
        return;
      }
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
      setMessages([]);
      setFeatureText("");
      hasSetTitle.current = false;
      reset();
    }

    if (sessionId !== null) {
      fetchMessages(sessionId).then((fetched) => {
        const mapped = fetched.map((m) => ({
          id: crypto.randomUUID(),
          role: m.role,
          content: m.content,
          responseType: null,
          timestamp: new Date(),
        }));
        setMessages(mapped);
        if (mapped.length > 0) hasSetTitle.current = true;
      });
    }
  }, [sessionId, reset, fetchMessages]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, status, scrollToBottom]);

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

      <main className="chat-layout">
        <div className="chat-messages" ref={messagesRef}>
          {messages.map((msg) => (
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
              {responseType === "report" && <ReportDocument content={tokens} done={status === "complete"} />}
              {responseType && responseType !== "report" && <PlainTextDisplay text={tokens} />}
            </div>
          )}

          {status === "error" && !tokens && (
            <div className="chat-message chat-message--assistant">
              <StatusIndicator status={status} message={statusMessage} error={error} />
            </div>
          )}

          {error && <ErrorDisplay error={error} />}
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
    </div>
  );
}
