export default function FeatureTextarea({ value, onChange, maxLength = 5000, disabled, compact, onKeyDown }) {
  const rows = compact ? 2 : 8;
  return (
    <textarea
      className={`feature-textarea ${compact ? "feature-textarea--compact" : ""}`}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={onKeyDown}
      placeholder={compact ? "Type your message..." : "Describe your feature for alignment auditing..."}
      maxLength={maxLength}
      rows={rows}
      disabled={disabled}
    />
  );
}
