import { useCallback, useRef, useState } from "react";
import { extractErrorMessage } from "../services/alignApi";

export function useStream() {
  const [status, setStatus] = useState("idle");
  const [responseType, setResponseType] = useState(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [tokens, setTokens] = useState("");
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  const reset = useCallback(() => {
    setStatus("idle");
    setResponseType(null);
    setStatusMessage("");
    setTokens("");
    setError(null);
  }, []);

  const consume = useCallback(async (response, onEvent) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6);
        if (!data) continue;

        try {
          const event = JSON.parse(data);
          onEvent?.(event);

          switch (event.type) {
            case "start":
              setResponseType(event.response_type);
              break;
            case "status":
              setStatusMessage(event.message);
              break;
            case "token":
              setTokens((prev) => prev + event.data);
              break;
            case "done":
              setStatus("complete");
              break;
            case "error":
              setError(event.message);
              setStatus("error");
              break;
          }
        } catch (err) {
          // The backend only ever sends well-formed JSON payloads; a parse
          // failure here means a truncated chunk or a proxy/dev-server
          // mangling the stream. Surfacing it (without breaking the stream)
          // makes that visible instead of silently dropping tokens.
          console.warn("Skipping malformed SSE line:", line, err);
        }
      }
    }
  }, []);

  const startStream = useCallback(
    async (fetchFn) => {
      reset();
      setStatus("connecting");

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const response = await fetchFn(controller.signal);
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(
            extractErrorMessage(body.detail, `Request failed: ${response.status}`)
          );
        }
        setStatus("streaming");
        await consume(response);
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(err.message);
          setStatus("error");
        }
      }
    },
    [consume, reset]
  );

  const abort = useCallback(() => {
    abortRef.current?.abort();
    setStatus("idle");
  }, []);

  const setErrorState = useCallback((message) => {
    setError(message);
    setStatus("error");
    setStatusMessage(message);
  }, []);

  return { status, responseType, statusMessage, tokens, error, startStream, abort, reset, setError: setErrorState, setStatus, setStatusMessage };
}
