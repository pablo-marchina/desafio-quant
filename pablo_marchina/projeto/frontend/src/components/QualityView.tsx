import { useEffect, useState } from "react";
import type { ProductQualitySummaryRead } from "../api/types";
import { getQualityReport } from "../api/product";
import { QualitySummaryPanel } from "./QualitySummaryPanel";

export function QualityView() {
  const [quality, setQuality] = useState<ProductQualitySummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const report = await getQualityReport();
      const mapped: ProductQualitySummaryRead = {
        analysis_run_id: "",
        quality_run_id: report.last_updated,
        status: report.status,
        evaluator_version: null,
        overall_status: report.status === "pass" ? "PASS" : report.status === "warn" ? "WARN" : "FAIL",
        total_metrics: Object.keys(report.metrics).length,
        passed_metrics: Object.values(report.metrics).filter((m: any) => m.passed).length,
        failed_metrics: Object.values(report.metrics).filter((m: any) => !m.passed).length,
        export_readiness_score: null,
        review_readiness_score: null,
        degraded_reason: null,
        metrics: report.metrics as Record<string, Record<string, any>>,
      };
      setQuality(mapped);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="quality-page">
      <div className="panel">
        <div className="panel-header">
          <h2>Quality Report</h2>
          <div className="panel-header-actions">
            <button type="button" className="secondary-button" onClick={load}>Refresh</button>
          </div>
        </div>
        <div className="panel-body">
          {error && (
            <div className="message error-message">{error}</div>
          )}
          {!error && loading && (
            <p className="loading-text">Loading quality report...</p>
          )}
          {!error && !loading && quality && (
            <QualitySummaryPanel quality={quality} />
          )}
          {!error && !loading && !quality && (
            <p className="empty-state">No quality report available.</p>
          )}
        </div>
      </div>
    </div>
  );
}