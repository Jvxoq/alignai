export default function CharacterCounter({ current, max }) {
  const ratio = current / max;
  const atLimit = current >= max;
  const warning = !atLimit && ratio > 0.9;

  const className = `char-counter ${
    atLimit ? "char-counter--error" : warning ? "char-counter--warning" : ""
  }`.trim();

  return <span className={className}>{current} / {max}</span>;
}
