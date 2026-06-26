export default function AuditButton({ onClick, disabled, loading, compact }) {
  return (
    <button
      className={`audit-button ${loading ? "audit-button--loading" : ""}`}
      onClick={onClick}
      disabled={disabled || loading}
    >
      {loading && (
        <svg className="audit-spinner" viewBox="0 0 24 24" width="14" height="14">
          <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="3" strokeDasharray="31.4" strokeDashoffset="10" strokeLinecap="round" />
        </svg>
      )}
      {loading ? "Auditing..." : compact ? "Send" : "Audit for Compliance"}
    </button>
  );
}
