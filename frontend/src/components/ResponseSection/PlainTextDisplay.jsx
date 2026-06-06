export default function PlainTextDisplay({ text }) {
  if (!text) return null;

  return (
    <div className="plain-text-display">
      <pre>{text}</pre>
    </div>
  );
}
