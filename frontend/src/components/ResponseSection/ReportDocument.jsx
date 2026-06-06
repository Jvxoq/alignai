export default function ReportDocument({ report }) {
  if (!report) return null;

  return (
    <div className="report-document">
      <h2>Alignment Report</h2>
      <div className="report-content">
        {report.split("\n").map((line, i) => {
          if (line.startsWith("## ")) {
            return <h3 key={i}>{line.slice(3)}</h3>;
          }
          if (line.startsWith("**") && line.endsWith("**")) {
            return <p key={i}><strong>{line.slice(2, -2)}</strong></p>;
          }
          if (line.startsWith("- ")) {
            return <li key={i}>{line.slice(2)}</li>;
          }
          if (!line.trim()) return <br key={i} />;
          return <p key={i}>{line}</p>;
        })}
      </div>
    </div>
  );
}
