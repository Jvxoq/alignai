import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import LoginForm from "./components/Auth/LoginForm";
import SignupForm from "./components/Auth/SignupForm";
import AuthLayout from "./components/Auth/AuthLayout";
import ProtectedRoute from "./components/Layout/ProtectedRoute";
import AppShell from "./components/Layout/AppShell";
import { SessionProvider } from "./context/SessionContext";
import { warmServices } from "./services/authApi";
import AlignPage from "./pages/AlignPage";

export default function App() {
  // Nudge the sleeping free-tier services awake as soon as the app loads —
  // before the visitor even signs in — so their first real request isn't stuck
  // behind a cold start. Runs on mount (StrictMode invokes it twice in dev, once
  // in production); the call is idempotent and best-effort, so failures and
  // duplicates are harmless.
  useEffect(() => {
    warmServices();
  }, []);

  return (
    <Routes>
      <Route path="/login" element={<AuthLayout><LoginForm /></AuthLayout>} />
      <Route path="/signup" element={<AuthLayout><SignupForm /></AuthLayout>} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <SessionProvider>
              <AppShell />
            </SessionProvider>
          </ProtectedRoute>
        }
      >
        <Route index element={<AlignPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
