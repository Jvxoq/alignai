import React from "react";

function PlainTextDisplayInner({ text }) {
  if (!text) return null;

  return (
    <div className="plain-text-display">
      <pre>{text}</pre>
    </div>
  );
}

export default React.memo(PlainTextDisplayInner);
