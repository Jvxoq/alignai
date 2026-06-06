export default function CharacterCounter({ current, max }) {
  const ratio = current / max;
  const warning = ratio > 0.9;

  return (
    <span className={`char-counter ${warning ? "char-counter--warning" : ""}`}>
      {current} / {max}
    </span>
  );
}
