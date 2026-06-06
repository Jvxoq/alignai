import { useCallback, useState } from "react";

const STORAGE_KEY = "alignai_session_id";

function generateSessionId() {
  return crypto.randomUUID();
}

export function useSession() {
  const [sessionId, setSessionId] = useState(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return stored;
    const id = generateSessionId();
    localStorage.setItem(STORAGE_KEY, id);
    return id;
  });

  const resetSession = useCallback(() => {
    const id = generateSessionId();
    localStorage.setItem(STORAGE_KEY, id);
    setSessionId(id);
    return id;
  }, []);

  return { sessionId, resetSession };
}
