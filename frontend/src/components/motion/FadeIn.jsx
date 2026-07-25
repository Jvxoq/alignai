import { motion, useReducedMotion } from "motion/react";
import { duration as durations, easeStandard, springs } from "../../lib/motion";

// Generic entrance wrapper: opacity+y together (never y alone -- a bare
// position change without fade reads as jumpy per the motion skill).
// `variant="card"` is the default -- content entering the viewport (report/
// chat message, CTA block), springs.card, y offset. `variant="fast"` is for
// status/alert banners -- opacity-only tween, no offset, since a spring on a
// tiny alert reads as overkill.
export default function FadeIn({ children, className, variant = "card", offset = 12, ...props }) {
  const reduceMotion = useReducedMotion();

  if (variant === "fast") {
    return (
      <motion.div
        className={className}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: durations.fast, ease: easeStandard }}
        {...props}
      >
        {children}
      </motion.div>
    );
  }

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: reduceMotion ? 0 : offset }}
      animate={{ opacity: 1, y: 0 }}
      transition={springs.card}
      {...props}
    >
      {children}
    </motion.div>
  );
}
