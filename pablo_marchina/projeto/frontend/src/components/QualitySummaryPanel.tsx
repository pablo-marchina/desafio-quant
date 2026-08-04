import type { ProductQualitySummaryRead } from "../api/types";

interface QualitySummaryPanelProps {
  quality: ProductQualitySummaryRead | null;
  loading?: boolean;
}

export function QualitySummaryPanel({ quality, loading }: QualitySummaryPanelProps) {
  if (loading) return <div className="panel"><div className="panel-body"><p className="loading-text">Loading quality...</p></div></div>;

  if (!quality) return null;

  const statusCls = quality.overall_status === "PASS"
    ? "cap-ok"
    : quality.overall_status === "WARN"
    ? "cap-warn"
    : "cap-bad";

  return (
    <div className="panel">
      <div className="panel-header"><h2>Quality</h2></div>
      <div className="panel-body">
        <div className="quality-header">
          <span className={`badge ${statusCls}`}>{quality.overall_status}</span>
          <span className="quality-stat">Export readiness: {quality.export_readiness_score?.toFixed(2) ?? "—"}</span>
          <span className="quality-stat">Review readiness: {quality.review_readiness_score?.toFixed(2) ?? "—"}</span>
        </div>

        {quality.degraded_reason && (
          <div className="message warning-message">{quality.degraded_reason}</div>
        )}

        <table className="data-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Value</th>
              <th>Threshold</th>
              <th>Passed</th>
              <th>Severity</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(quality.metrics).map(([name, metric]) => (
              <tr key={name}>
                <td>{name}</td>
                <td>{String(metric.metric_value ?? metric.value ?? "")}</td>
                <td>{String(metric.threshold ?? "")}</td>
                <td>
                  <span className={`badge ${metric.passed ? "cap-ok" : "cap-bad"}`}>
                    {metric.passed ? "PASS" : "FAIL"}
                  </span>
                </td>
                <td>{String(metric.severity ?? "")}</td>
              </tr>
            ))}
            {Object.keys(quality.metrics).length === 0 && (
              <tr><td colSpan={5} className="muted">No metrics available.</td></tr>
            )}
          </tbody>
        </table>

        <div className="quality-stats">
          <span>{quality.passed_metrics} passed / {quality.total_metrics} total</span>
          {quality.failed_metrics > 0 && (
            <span className="text-warn">{quality.failed_metrics} failed</span>
          )}
        </div>
      </div>
    </div>
  );
}
