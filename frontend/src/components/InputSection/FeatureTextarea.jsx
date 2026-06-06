export default function FeatureTextarea({ value, onChange, maxLength = 5000, disabled }) {
  return (
    <textarea
      className="feature-textarea"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder="Describe your feature for alignment auditing..."
      maxLength={maxLength}
      rows={8}
      disabled={disabled}
    />
  );
}
