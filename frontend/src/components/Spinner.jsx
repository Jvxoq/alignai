export default function Spinner({ size = 20, className = "" }) {
  return (
    <svg
      className={`spinner ${className}`}
      viewBox="0 0 24 24"
      width={size}
      height={size}
      role="presentation"
    >
      <circle
        cx="12"
        cy="12"
        r="10"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeDasharray="31.4"
        strokeDashoffset="10"
        strokeLinecap="round"
      />
    </svg>
  );
}
