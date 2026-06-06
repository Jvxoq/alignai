import { useState } from "react";
import AuditButton from "./components/InputSection/AuditButton";
import CharacterCounter from "./components/InputSection/CharacterCounter";
import FeatureTextarea from "./components/InputSection/FeatureTextarea";
import ErrorDisplay from "./components/ResponseSection/ErrorDisplay";
import PlainTextDisplay from "./components/ResponseSection/PlainTextDisplay";
import ReportDocument from "./components/ResponseSection/ReportDocument";
import StatusIndicator from "./components/ResponseSection/StatusIndicator";
import { useSession } from "./hooks/useSession";
import { useStream } from "./hooks/useStream";
import { postAlign } from "./services/alignApi";

const MAX_LENGTH = 5000;

export default function App() {
  const [featureText, setFeatureText] = useState("");
  const { sessionId } = useSession();
  const { status, tokens, report, error, startStream } = useStream();

  const isLoading = status === "connecting" || status === "streaming";
  const canSubmit = featureText.trim().length > 0 && !isLoading;

  const handleAudit = () => {
    startStream((signal) =>
      postAlign({ sessionId, featureText: featureText.trim(), signal })
    );
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>AlignAI</h1>
        <p>Feature alignment auditing powered by AI</p>
      </header>

      <main className="app-main">
        <section className="input-section">
          <FeatureTextarea
            value={featureText}
            onChange={setFeatureText}
            maxLength={MAX_LENGTH}
            disabled={isLoading}
          />
          <div className="input-footer">
            <CharacterCounter current={featureText.length} max={MAX_LENGTH} />
            <AuditButton onClick={handleAudit} disabled={!canSubmit} loading={isLoading} />
          </div>
        </section>

        <section className="response-section">
          <StatusIndicator status={status} />
          <ErrorDisplay error={error} />
          {isLoading && <PlainTextDisplay text={tokens} />}
          {report && <ReportDocument report={report} />}
        </section>
      </main>
    </div>
  );
}
