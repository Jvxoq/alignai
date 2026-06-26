import React from "react";

const STATUS_LABELS = {
  idle: "Ready",
  connecting: "Connecting...",
  streaming: "Analyzing...",
  complete: "Complete",
  error: "Error",
};

function StatusIndicatorInner({ status, message, error }) {
  const label = message || STATUS_LABELS[status] || status;
  const isActive = status === "connecting" || status === "streaming";
  const isError = status === "error" || error;

  if (!isActive && !isError) return null;

  return (
    <div className={`status-indicator ${isError ? "status-indicator--error" : "status-indicator--active"}`}>
      {!isError && <span className="status-dot" />}
      <span>{isError ? (error || "An error occurred") : label}</span>
    </div>
  );
}

export default React.memo(StatusIndicatorInner);
