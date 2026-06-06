import { useCallback, useRef, useState } from "react";

export function useStream() {
  const [status, setStatus] = useState("idle");
  const [tokens, setTokens] = useState("");
  const [report, setReport] = useState("");
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  const reset = useCallback(() => {
    setStatus("idle");
    setTokens("");
    setReport("");
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
            case "status":
              setStatus(event.message);
              break;
            case "token":
              setTokens((prev) => prev + event.content);
              break;
            case "done":
              setReport(event.report);
              setStatus("complete");
              break;
            case "error":
              setError(event.message);
              setStatus("error");
              break;
          }
        } catch {
          // skip malformed SSE lines
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
          throw new Error(`Request failed: ${response.status}`);
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

  return { status, tokens, report, error, startStream, abort, reset };
}
