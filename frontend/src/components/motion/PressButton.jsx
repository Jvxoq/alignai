import { motion, useReducedMotion } from "motion/react";
import { springs } from "../../lib/motion";

// Shared button press feedback: scale 0.97 on tap via springs.press, no
// hover scale/lift (this system stays flat on hover -- only default->active
// color changes there). Skipped entirely under reduced motion.
export default function PressButton({ children, disabled, ...props }) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.button
      disabled={disabled}
      whileTap={disabled || reduceMotion ? undefined : { scale: 0.97 }}
      transition={springs.press}
      {...props}
    >
      {children}
    </motion.button>
  );
}
