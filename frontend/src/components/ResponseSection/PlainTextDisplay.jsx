import React from "react";
import FadeIn from "../motion/FadeIn";

function PlainTextDisplayInner({ text }) {
  if (!text) return null;

  return (
    <FadeIn className="plain-text-display">
      <pre>{text}</pre>
    </FadeIn>
  );
}

export default React.memo(PlainTextDisplayInner);
