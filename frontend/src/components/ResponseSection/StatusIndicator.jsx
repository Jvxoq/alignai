const STATUS_LABELS = {
  idle: "Ready",
  connecting: "Connecting...",
  streaming: "Generating report...",
  complete: "Complete",
  error: "Error",
};

export default function StatusIndicator({ status }) {
  const label = STATUS_LABELS[status] || status;
  const isActive = status === "connecting" || status === "streaming";

  return (
    <div className={`status-indicator ${isActive ? "status-indicator--active" : ""}`}>
      <span className="status-dot" />
      <span>{label}</span>
    </div>
  );
}
