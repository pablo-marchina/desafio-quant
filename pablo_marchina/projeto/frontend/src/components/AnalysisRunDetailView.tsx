import { useEffect, useState } from "react";
import type { AnalysisEvidenceBundle, AnalysisRunRead, ProductQualitySummaryRead } from "../api/types";
import { getAnalysisEvidenceBundle, getAnalysisRun, getQualitySummary } from "../api/product";
import { EvidenceFirstRunView } from "./EvidenceFirstRunView";

interface AnalysisRunDetailViewProps {
  runId: string;
  onBack: () => void;
  onViewDossier: (runId: string) => void;
}

function statusBadge(status: string): { cls: string; text: string } {
  switch (status) {
    case "completed": return { cls: "cap-ok", text: "Completed" };
    case "degraded": return { cls: "cap-warn", text: "Degraded" };
    case "failed": return { cls: "cap-bad", text: "Failed" };
    case "running": return { cls: "cap-exp", text: "Running" };
    case "queued": return { cls: "cap-off", text: "Queued" };
    default: return { cls: "cap-off", text: status };
  }
}

export function AnalysisRunDetailView({
  runId,
  onBack,
  onViewDossier,
}: AnalysisRunDetailViewProps) {
  const [run, setRun] = useState<AnalysisRunRead | null>(null);
  const [bundle, setBundle] = useState<AnalysisEvidenceBundle | null>(null);
  const [quality, setQuality] = useState<ProductQualitySummaryRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [r, evidenceBundle, q] = await Promise.all([
        getAnalysisRun(runId),
        getAnalysisEvidenceBundle(runId).catch(() => null),
        getQualitySummary(runId).catch(() => null),
      ]);
      setRun(r);
      setBundle(evidenceBundle);
      setQuality(q);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [runId]);

  if (loading) return <div className="panel"><div className="panel-body"><p className="loading-text">Loading analysis run...</p></div></div>;

  if (error) {
    return (
      <div className="panel">
        <div className="panel-body">
          <div className="message error-message">{error}</div>
          <button type="button" className="secondary-button" onClick={load}>Retry</button>
        </div>
      </div>
    );
  }

  if (!run) return null;

  const st = statusBadge(run.status);
  const cs = run.claim_summary;

  return (
    <div className="analysis-run-page">
      <div className="panel">
        <div className="panel-header">
          <div className="panel-header-left">
            <button type="button" className="back-button" onClick={onBack}>← Back</button>
            <h2>Analysis Run</h2>
          </div>
          <button type="button" className="secondary-button" onClick={load}>Refresh</button>
        </div>
        <div className="panel-body">
          <table className="data-table">
            <tbody>
              <tr><td className="label-cell">ID</td><td><code>{run.id}</code></td></tr>
              <tr><td className="label-cell">Status</td><td><span className={`badge ${st.cls}`}>{st.text}</span></td></tr>
              <tr><td className="label-cell">Pipeline Version</td><td>{run.pipeline_version}</td></tr>
              <tr><td className="label-cell">Corpus Version</td><td>{run.corpus_version || <span className="muted">—</span>}</td></tr>
              <tr><td className="label-cell">Started</td><td>{run.started_at ? new Date(run.started_at).toLocaleString() : <span className="muted">—</span>}</td></tr>
              <tr><td className="label-cell">Completed</td><td>{run.completed_at ? new Date(run.completed_at).toLocaleString() : <span className="muted">—</span>}</td></tr>
              {run.degraded_reason && <tr><td className="label-cell">Degraded Reason</td><td className="text-warn">{run.degraded_reason}</td></tr>}
              {run.error_message && <tr><td className="label-cell">Error</td><td className="text-error">{run.error_message}</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      <EvidenceFirstRunView bundle={bundle} />

      {run.scores.length > 0 && (
        <div className="panel">
          <div className="panel-header"><h2>Scores</h2></div>
          <div className="panel-body">
            <div className="score-grid-compact">
              {run.scores.map((s, i) => (
                <div key={i} className="score-card-compact">
                  <span className="score-label">{String(s.score_type || "")}</span>
                  <strong className="score-value">{String(s.value ?? "")}</strong>
                  {s.confidence && <span className="score-confidence">{String(s.confidence)}</span>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {cs && (
        <div className="panel">
          <div className="panel-header"><h2>Claims & Evidence</h2></div>
          <div className="panel-body">
            <div className="claim-summary-grid">
              <div className="claim-stat"><span>Total</span><strong>{cs.total_claims}</strong></div>
              <div className="claim-stat"><span>Supported</span><strong>{cs.supported_claims}</strong></div>
              <div className="claim-stat"><span>Unsupported</span><strong className="text-warn">{cs.unsupported_claims}</strong></div>
              <div className="claim-stat"><span>Coverage</span><strong>{Math.round(cs.evidence_coverage * 100)}%</strong></div>
            </div>
          </div>
        </div>
      )}

      {run.gaps.length > 0 && (
        <div className="panel">
          <div className="panel-header"><h2>Detected Gaps</h2></div>
          <div className="panel-body">
            <table className="data-table">
              <thead>
                <tr><th>Gap Type</th><th>Confidence</th><th>Evidence</th><th>Reasoning</th></tr>
              </thead>
              <tbody>
                {run.gaps.map((g, i) => (
                  <tr key={i}>
                    <td><strong>{String(g.gap_type || "")}</strong></td>
                    <td>{String(g.confidence || "")}</td>
                    <td><span className={`badge ev-${String(g.evidence_tag || "inferred")}`}>{String(g.evidence_tag || "")}</span></td>
                    <td className="reasoning-cell">{String(g.reasoning || "")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {run.nvidia_mappings.length > 0 && (
        <div className="panel">
          <div className="panel-header"><h2>NVIDIA Technology Mappings</h2></div>
          <div className="panel-body">
            <table className="data-table">
              <thead>
                <tr><th>Technology</th><th>Addresses Gap</th><th>Action</th><th>Priority</th></tr>
              </thead>
              <tbody>
                {run.nvidia_mappings.map((m, i) => (
                  <tr key={i}>
                    <td><strong>{String(m.technology_name || "")}</strong></td>
                    <td>{String(m.addresses_gap || "")}</td>
                    <td>{String(m.recommendation_action || "")}</td>
                    <td>{String(m.priority || "")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {run.readiness_checks.length > 0 && (
        <div className="panel">
          <div className="panel-header"><h2>Readiness Checks</h2></div>
          <div className="panel-body">
            {run.readiness_checks.map((rc, i) => (
              <div key={i} className={`readiness-row severity-${rc.severity}`}>
                <span className="readiness-code">{rc.code}</span>
                <span className="readiness-msg">{rc.user_message}</span>
                {rc.recommended_action && (
                  <span className="readiness-action">{rc.recommended_action}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {quality && (
        <div className="panel">
          <div className="panel-header"><h2>Quality Summary</h2></div>
          <div className="panel-body">
            <div className="quality-status-row">
              <span className={`badge ${quality.overall_status === "PASS" ? "cap-ok" : quality.overall_status === "WARN" ? "cap-warn" : "cap-bad"}`}>
                {quality.overall_status}
              </span>
              <span className="quality-stat">Export: {quality.export_readiness_score ?? "—"}</span>
              <span className="quality-stat">Review: {quality.review_readiness_score ?? "—"}</span>
            </div>
            {quality.degraded_reason && (
              <div className="message warning-message">{quality.degraded_reason}</div>
            )}
          </div>
        </div>
      )}

      <div className="panel">
        <div className="panel-header"><h2>Actions</h2></div>
        <div className="panel-body">
          <div className="action-buttons">
            <button
              type="button"
              className="secondary-button"
              onClick={() => onViewDossier(runId)}
              disabled={!run.dossier_summary?.dossier_available}
            >
              {run.dossier_summary?.dossier_available ? "View Dossier" : "Dossier Not Available"}
            </button>
            {run.action_brief_id && (
              <span className="muted">Brief ID: {run.action_brief_id}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
