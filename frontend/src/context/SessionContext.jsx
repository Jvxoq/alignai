import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { request } from "../services/authApi";
import { useAuth } from "../hooks/useAuth";

const STORAGE_KEY = "alignai_active_session_id";

const SessionContext = createContext(null);

export function SessionProvider({ children }) {
  const { isAuthenticated } = useAuth();
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(STORAGE_KEY));
  const [sessions, setSessions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const fetchedRef = useRef(false);

  const fetchSessions = useCallback(async () => {
    try {
      const response = await request("/sessions");
      if (response && response.ok) {
        const data = await response.json();
        const list = data.sessions || [];
        setSessions(list);
        setSessionId((prev) => {
          if (prev && list.some((s) => s.id === prev)) return prev;
          const fallback = list.length > 0 ? list[0].id : null;
          if (fallback) localStorage.setItem(STORAGE_KEY, fallback);
          else localStorage.removeItem(STORAGE_KEY);
          return fallback;
        });
      }
    } catch (err) {
      console.error("Failed to fetch sessions:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated && !fetchedRef.current) {
      fetchedRef.current = true;
      fetchSessions();
    }
    if (!isAuthenticated) {
      fetchedRef.current = false;
      setSessions([]);
      setSessionId(null);
      setIsLoading(true);
    }
  }, [isAuthenticated, fetchSessions]);

  const createSession = useCallback(async () => {
    try {
      const response = await request("/sessions", { method: "POST" });
      if (response && response.ok) {
        const data = await response.json();
        setSessions((prev) => [data, ...prev]);
        setSessionId(data.id);
        localStorage.setItem(STORAGE_KEY, data.id);
        return data.id;
      }
    } catch (err) {
      console.error("Failed to create session:", err);
    }
    return null;
  }, []);

  const sessionsRef = useRef(sessions);
  sessionsRef.current = sessions;

  const deleteSession = useCallback(async (id) => {
    try {
      const response = await request(`/sessions/${id}`, { method: "DELETE" });
      if (response && response.ok) {
        const remaining = sessionsRef.current.filter((s) => s.id !== id);
        setSessions(remaining);
        if (sessionId === id) {
          const newId = remaining.length > 0 ? remaining[0].id : null;
          setSessionId(newId);
          if (newId) localStorage.setItem(STORAGE_KEY, newId);
          else localStorage.removeItem(STORAGE_KEY);
        }
        return true;
      }
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
    return false;
  }, [sessionId]);

  const setActiveSession = useCallback((id) => {
    setSessionId(id);
    localStorage.setItem(STORAGE_KEY, id);
  }, []);

  const updateSessionTitle = useCallback(async (id, title) => {
    try {
      const response = await request(`/sessions/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      });
      if (response && response.ok) {
        setSessions((prev) => prev.map((s) => (s.id === id ? { ...s, title } : s)));
        return true;
      }
    } catch (err) {
      console.error("Failed to update session title:", err);
    }
    return false;
  }, []);

  const clearSession = useCallback(() => {
    setSessionId(null);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  const fetchMessages = useCallback(async (sessionId) => {
    try {
      const response = await request(`/sessions/${sessionId}/messages`);
      if (response && response.ok) {
        const data = await response.json();
        return data.messages || [];
      }
    } catch (err) {
      console.error("Failed to fetch messages:", err);
    }
    return [];
  }, []);

  return (
    <SessionContext.Provider value={{ sessionId, sessions, isLoading, createSession, clearSession, deleteSession, setActiveSession, updateSessionTitle, fetchMessages, refreshSessions: fetchSessions }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSessionContext() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSessionContext must be used within a SessionProvider");
  }
  return context;
}