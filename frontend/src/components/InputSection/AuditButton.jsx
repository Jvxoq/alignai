export default function AuditButton({ onClick, disabled, loading }) {
  return (
    <button
      className="audit-button"
      onClick={onClick}
      disabled={disabled || loading}
    >
      {loading ? "Auditing..." : "Run Alignment Audit"}
    </button>
  );
}
