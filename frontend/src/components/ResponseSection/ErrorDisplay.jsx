import FadeIn from "../motion/FadeIn";

export default function ErrorDisplay({ error }) {
  if (!error) return null;

  return (
    <FadeIn variant="fast" className="error-display" role="alert">
      <strong>Error:</strong> {error}
    </FadeIn>
  );
}
