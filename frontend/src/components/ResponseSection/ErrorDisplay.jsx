export default function ErrorDisplay({ error }) {
  if (!error) return null;

  return (
    <div className="error-display" role="alert">
      <strong>Error:</strong> {error}
    </div>
  );
}
