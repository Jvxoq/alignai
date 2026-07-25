import React from "react";
import ReactMarkdown from "react-markdown";
import FadeIn from "../motion/FadeIn";

function ReportDocumentInner({ content }) {
  if (!content) return null;
  return (
    <article className="report-document">
      <FadeIn className="report-document-markdown">
        <ReactMarkdown>{content}</ReactMarkdown>
      </FadeIn>
    </article>
  );
}

export default React.memo(ReportDocumentInner);
