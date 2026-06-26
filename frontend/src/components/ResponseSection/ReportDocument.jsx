import React from "react";
import ReactMarkdown from "react-markdown";

function ReportDocumentInner({ content, done }) {
  if (!content) return null;
  return (
    <article className="report-document">
      {done ? (
        <ReactMarkdown>{content}</ReactMarkdown>
      ) : (
        <pre className="report-document-raw">{content}</pre>
      )}
    </article>
  );
}

export default React.memo(ReportDocumentInner);
