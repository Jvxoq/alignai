import { useEffect } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import LoginForm from "./components/Auth/LoginForm";
import SignupForm from "./components/Auth/SignupForm";
import AuthLayout from "./components/Auth/AuthLayout";
import AppShell from "./components/Layout/AppShell";
import Spinner from "./components/Spinner";
import { SessionProvider } from "./context/SessionContext";
import { useAuth } from "./hooks/useAuth";
import { warmServices } from "./services/authApi";
import AlignPage from "./pages/AlignPage";
import LandingPage from "./pages/LandingPage";
import { springs } from "./lib/motion";

// Per-route content wrapper: opacity+y entrance via springs.standard, a fast
// 150ms opacity-only exit (exits should be quicker than entrances -- never
// make a user wait on something leaving). Relies on the AnimatePresence
// further up (keyed on the URL, in App below) to actually trigger the exit;
// this is just the motion node it animates.
function PageTransition({ children }) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      initial={{ opacity: 0, y: reduceMotion ? 0 : 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, transition: { duration: 0.15 } }}
      transition={springs.standard}
    >
      {children}
    </motion.div>
  );
}

// The "/" route branches on auth state rather than redirecting -- an
// unauthenticated visitor gets the LandingPage trial instead of being bounced
// to /login. The URL stays "/" across that branch (loading -> landing ->
// full app), so it needs its own AnimatePresence, keyed on auth state, to
// catch the swap -- the route-level one below never sees a key change here.
function RootRoute() {
  const { isAuthenticated, isLoading } = useAuth();
  const reduceMotion = useReducedMotion();
  const stateKey = isLoading ? "loading" : isAuthenticated ? "app" : "landing";

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={stateKey}
        initial={{ opacity: 0, y: reduceMotion ? 0 : 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, transition: { duration: 0.15 } }}
        transition={springs.standard}
      >
        {isLoading ? (
          <div className="loading-screen">
            <Spinner size={28} />
            <span>Loading...</span>
          </div>
        ) : isAuthenticated ? (
          <SessionProvider>
            <AppShell />
          </SessionProvider>
        ) : (
          <LandingPage />
        )}
      </motion.div>
    </AnimatePresence>
  );
}

export default function App() {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  // Nudge the sleeping free-tier services awake as soon as the app loads —
  // before the visitor even signs in — so their first real request isn't stuck
  // behind a cold start. Runs on mount (StrictMode invokes it twice in dev, once
  // in production); the call is idempotent and best-effort, so failures and
  // duplicates are harmless.
  useEffect(() => {
    warmServices();
  }, []);

  return (
    <AnimatePresence mode="wait" initial={false}>
      <Routes location={location} key={location.pathname}>
        <Route
          path="/login"
          element={<AuthLayout><PageTransition><LoginForm /></PageTransition></AuthLayout>}
        />
        <Route
          path="/signup"
          element={<AuthLayout><PageTransition><SignupForm /></PageTransition></AuthLayout>}
        />
        <Route path="/" element={<RootRoute />}>
          {isAuthenticated && <Route index element={<AlignPage />} />}
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AnimatePresence>
  );
}
