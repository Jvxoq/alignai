import { Routes, Route, Navigate } from "react-router-dom";
import LoginForm from "./components/Auth/LoginForm";
import SignupForm from "./components/Auth/SignupForm";
import AuthLayout from "./components/Auth/AuthLayout";
import ProtectedRoute from "./components/Layout/ProtectedRoute";
import AppShell from "./components/Layout/AppShell";
import { SessionProvider } from "./context/SessionContext";
import AlignPage from "./pages/AlignPage";

export default function App() {
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
