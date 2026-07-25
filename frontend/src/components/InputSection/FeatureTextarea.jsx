import { motion } from "motion/react";
import { duration, easeStandard } from "../../lib/motion";

export default function FeatureTextarea({ value, onChange, maxLength = 5000, disabled, compact, onKeyDown }) {
  const rows = compact ? 2 : 8;
  return (
    <motion.textarea
      className={`feature-textarea ${compact ? "feature-textarea--compact" : ""}`}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={onKeyDown}
      placeholder={compact ? "Type your message..." : "Describe your feature for alignment auditing..."}
      maxLength={maxLength}
      rows={rows}
      disabled={disabled}
      // Focus ring: boxShadow tween, never a spring -- springs on shadow
      // values look glitchy.
      whileFocus={{ boxShadow: "0 0 0 3px rgba(255, 255, 255, 0.15)" }}
      transition={{ duration: duration.fast, ease: easeStandard }}
    />
  );
}
