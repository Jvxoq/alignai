import React from "react";
import ReactMarkdown from "react-markdown";

function ReportDocumentInner({ content }) {
  if (!content) return null;
  return (
    <article className="report-document">
      <div className="report-document-markdown">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    </article>
  );
}

export default React.memo(ReportDocumentInner);
