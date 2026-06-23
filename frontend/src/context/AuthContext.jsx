import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { login as apiLogin, signup as apiSignup, logout as apiLogout, deleteAccount as apiDeleteAccount, request, getAccessToken } from "../services/authApi";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      setIsAuthenticated(false);
      setIsLoading(false);
      return;
    }
    try {
      const response = await request("/auth/me");
      if (response && response.ok) {
        const data = await response.json();
        setUser(data);
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch {
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    const handleUnauthorized = () => {
      setUser(null);
      setIsAuthenticated(false);
    };
    window.addEventListener("auth:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("auth:unauthorized", handleUnauthorized);
  }, []);

  const login = async (email, password) => {
    await apiLogin(email, password);
    setIsAuthenticated(true);
  };

  const signup = async (email, password) => {
    await apiSignup(email, password);
    setIsAuthenticated(true);
  };

  const logout = async () => {
    await apiLogout();
    setIsAuthenticated(false);
    setUser(null);
  };

  const deleteAccount = async () => {
    const success = await apiDeleteAccount();
    if (success) {
      setIsAuthenticated(false);
      setUser(null);
    }
    return success;
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, isLoading, login, signup, logout, deleteAccount }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}