import { useState } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "motion/react";
import AuditButton from "../components/InputSection/AuditButton";
import CharacterCounter from "../components/InputSection/CharacterCounter";
import FeatureTextarea from "../components/InputSection/FeatureTextarea";
import ErrorDisplay from "../components/ResponseSection/ErrorDisplay";
import PlainTextDisplay from "../components/ResponseSection/PlainTextDisplay";
import ReportDocument from "../components/ResponseSection/ReportDocument";
import StatusIndicator from "../components/ResponseSection/StatusIndicator";
import FadeIn from "../components/motion/FadeIn";
import { useStream } from "../hooks/useStream";
import { postTrialAlign } from "../services/trialApi";
import { springs } from "../lib/motion";

const MAX_LENGTH = 2000;

// Wraps react-router's Link so it can take whileTap press feedback, same as
// every other button in the app -- this system doesn't hover-scale, but a
// tap/click still gets the springs.press squeeze.
const MotionLink = motion.create(Link);

export default function LandingPage() {
  const [featureText, setFeatureText] = useState("");
  // Set the moment submit fires, before we know the outcome -- the trial is
  // "used" whether the request succeeds, errors, or the cookie was already
  // spent on a prior visit (an immediate 403). Once true, the input stays
  // hidden and the sign-in CTA is shown, for every one of those cases alike.
  const [attempted, setAttempted] = useState(false);
  const { status, responseType, statusMessage, tokens, error, startStream } = useStream();
  const reduceMotion = useReducedMotion();
  const messageEntrance = {
    initial: { opacity: 0, y: reduceMotion ? 0 : 12 },
    animate: { opacity: 1, y: 0 },
    transition: springs.card,
  };
  const press = { whileTap: reduceMotion ? undefined : { scale: 0.97 }, transition: springs.press };

  const isLoading = status === "connecting" || status === "streaming";
  const canSubmit = featureText.trim().length > 0 && !isLoading && !attempted;

  const handleSubmit = () => {
    const text = featureText.trim();
    if (!text || isLoading || attempted) return;

    setAttempted(true);
    setFeatureText("");
    startStream((signal) => postTrialAlign({ featureText: text, signal }));
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSubmit) handleSubmit();
    }
  };

  return (
    <div className="app">
      {/* Once the trial is used, the CTA below the answer already offers
          sign in / sign up -- a second sign-in entry point up here would be
          redundant, so it only shows while the trial is still available. */}
      {!attempted && (
        <MotionLink to="/login" className="landing-signin" {...press}>Sign in</MotionLink>
      )}

      <header className="app-header">
        <h1>AlignAI</h1>
        <p>Feature alignment auditing powered by AI -- try it free, no account needed</p>
      </header>

      <main className="chat-layout">
        <div className="chat-messages">
          {(status === "streaming" || status === "complete") && (
            <motion.div className="chat-message chat-message--assistant" {...messageEntrance}>
              {!tokens && <StatusIndicator status={status} message={statusMessage} error={error} />}
              {tokens && (
                <div className="chat-message-content">
                  {responseType === "report" && <ReportDocument content={tokens} />}
                  {responseType && responseType !== "report" && <PlainTextDisplay text={tokens} />}
                </div>
              )}
            </motion.div>
          )}

          {status === "error" && tokens && (
            <motion.div className="chat-message chat-message--assistant" {...messageEntrance}>
              <div className="chat-message-content">
                {responseType === "report" && <ReportDocument content={tokens} />}
                {responseType && responseType !== "report" && <PlainTextDisplay text={tokens} />}
              </div>
            </motion.div>
          )}

          {status === "error" && !tokens && (
            <motion.div className="chat-message chat-message--assistant" {...messageEntrance}>
              <StatusIndicator status={status} message={statusMessage} error={error} />
            </motion.div>
          )}

          {error && tokens && <ErrorDisplay error={error} />}
        </div>

        {!attempted && (
          <div className="chat-input-container">
            <section className="input-section">
              <FeatureTextarea
                value={featureText}
                onChange={setFeatureText}
                maxLength={MAX_LENGTH}
                disabled={isLoading}
                onKeyDown={handleKeyDown}
              />
              <div className="input-footer">
                <CharacterCounter current={featureText.length} max={MAX_LENGTH} />
                <AuditButton onClick={handleSubmit} disabled={!canSubmit} loading={isLoading} />
              </div>
            </section>
          </div>
        )}

        {attempted && (
          <FadeIn className="trial-cta">
            <p>Like what you see? Sign in to keep going.</p>
            <div className="trial-cta-actions">
              <MotionLink to="/signup" className="auth-button" {...press}>Sign up</MotionLink>
              <MotionLink to="/login" className="trial-cta-secondary" {...press}>Log in</MotionLink>
            </div>
          </FadeIn>
        )}
      </main>
    </div>
  );
}
