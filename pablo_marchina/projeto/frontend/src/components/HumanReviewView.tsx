import { useEffect, useState } from "react";
import type { ProductWorkflowRunRead, WorkflowReviewPayload, WorkflowReviewDecisionRead } from "../api/types";
import { getWorkflowReviewPayload, submitWorkflowReview, listWorkflowRuns } from "../api/product";

const DECISIONS = ["approve", "reject", "request_more_evidence"];

export function HumanReviewView() {
  const [workflowId, setWorkflowId] = useState("");
  const [payload, setPayload] = useState<WorkflowReviewPayload | null>(null);
  const [loadingPayload, setLoadingPayload] = useState(false);
  const [payloadError, setPayloadError] = useState<string | null>(null);

  const [decision, setDecision] = useState(DECISIONS[0]);
  const [reviewer, setReviewer] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitResult, setSubmitResult] = useState<WorkflowReviewDecisionRead | null>(null);

  const [runs, setRuns] = useState<ProductWorkflowRunRead[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(true);

  async function loadRuns() {
    setLoadingRuns(true);
    try {
      const resp = await listWorkflowRuns();
      setRuns(resp.items);
    } catch {
      setRuns([]);
    } finally {
      setLoadingRuns(false);
    }
  }

  useEffect(() => { loadRuns(); }, []);

  async function handleFetchPayload(id: string) {
    const targetId = id || workflowId;
    if (!targetId.trim()) return;
    setLoadingPayload(true);
    setPayloadError(null);
    setPayload(null);
    setSubmitResult(null);
    try {
      const p = await getWorkflowReviewPayload(targetId.trim());
      setPayload(p);
      setWorkflowId(targetId.trim());
    } catch (err) {
      setPayloadError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingPayload(false);
    }
  }

  async function handleSubmit() {
    if (!reviewer.trim()) {
      setSubmitError("Reviewer name is required.");
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    setSubmitResult(null);
    try {
      const result = await submitWorkflowReview(workflowId, decision, reviewer.trim(), notes.trim());
      setSubmitResult(result);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  function severityClass(severity: string): string {
    if (severity === "high") return "badge status-failed";
    if (severity === "medium") return "badge status-degraded";
    return "badge status-pass";
  }

  return (
    <div className="human-review-page">
      <div className="panel">
        <div className="panel-header">
          <h2>Human Review</h2>
          <div className="panel-header-actions">
            <button type="button" className="secondary-button" onClick={loadRuns}>Refresh</button>
          </div>
        </div>
        <div className="panel-body">
          <div className="form-inline">
            <div className="form-field" style={{ flex: 3 }}>
              <label>Workflow ID</label>
              <input
                type="text"
                value={workflowId}
                onChange={(e) => setWorkflowId(e.target.value)}
                placeholder="Paste a workflow run ID"
              />
            </div>
            <div className="form-field" style={{ flex: 0 }}>
              <button
                type="button"
                className="primary-button"
                onClick={() => handleFetchPayload(workflowId)}
                disabled={loadingPayload || !workflowId.trim()}
                style={{ marginTop: 22 }}
              >
                {loadingPayload ? "Loading..." : "Load"}
              </button>
            </div>
          </div>

          {loadingRuns ? (
            <p className="loading-text">Loading workflow runs...</p>
          ) : runs.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <h3>Workflows Needing Review</h3>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Startup ID</th>
                    <th>Status</th>
                    <th>Current Node</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {runs.filter((r) => r.state && typeof r.state === "object" && "review_payload" in r.state).map((r) => (
                    <tr key={r.id}>
                      <td><code>{r.id.slice(0, 12)}...</code></td>
                      <td>{r.startup_id ? <code>{r.startup_id.slice(0, 12)}...</code> : <span className="muted">—</span>}</td>
                      <td><span className={`badge status-${r.status}`}>{r.status}</span></td>
                      <td>{r.current_node}</td>
                      <td>
                        <button type="button" className="link-button" onClick={() => handleFetchPayload(r.id)}>
                          Review
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {runs.filter((r) => r.state && typeof r.state === "object" && "review_payload" in r.state).length === 0 && (
                <p className="muted" style={{ marginTop: 8 }}>No workflows currently needing review.</p>
              )}
            </div>
          )}
        </div>
      </div>

      {loadingPayload && (
        <div className="panel"><div className="panel-body"><p className="loading-text">Loading review payload...</p></div></div>
      )}

      {payloadError && (
        <div className="panel"><div className="panel-body"><div className="message error-message">{payloadError}</div></div></div>
      )}

      {payload && !loadingPayload && (
        <>
          <div className="panel">
            <div className="panel-header"><h2>Review Payload</h2></div>
            <div className="panel-body">
              <table className="data-table">
                <tbody>
                  <tr><td className="label-cell">Run ID</td><td><code>{payload.run_id}</code></td></tr>
                  <tr><td className="label-cell">Startup ID</td><td><code>{payload.startup_id || "—"}</code></td></tr>
                  <tr><td className="label-cell">Severity</td><td><span className={severityClass(payload.severity)}>{payload.severity}</span></td></tr>
                  <tr><td className="label-cell">Reason</td><td>{payload.reason}</td></tr>
                  <tr><td className="label-cell">Resumable</td><td>{payload.resumable ? "Yes" : "No"}</td></tr>
                  <tr><td className="label-cell">Interrupt Enabled</td><td>{payload.interrupt_enabled ? "Yes" : "No"}</td></tr>
                </tbody>
              </table>

              {payload.failed_quality_checks.length > 0 && (
                <>
                  <h3 style={{ marginTop: 16, marginBottom: 8 }}>Failed Quality Checks</h3>
                  <ul className="check-list">
                    {payload.failed_quality_checks.map((c, i) => (
                      <li key={i} className="check-item fail">{c}</li>
                    ))}
                  </ul>
                </>
              )}

              {payload.blockers.length > 0 && (
                <>
                  <h3 style={{ marginTop: 16, marginBottom: 8 }}>Blockers</h3>
                  <ul className="check-list">
                    {payload.blockers.map((b, i) => (
                      <li key={i} className="check-item fail">{b}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          </div>

          <div className="panel">
            <div className="panel-header"><h2>Submit Decision</h2></div>
            <div className="panel-body">
              <div className="form-inline">
                <div className="form-field">
                  <label>Decision *</label>
                  <select value={decision} onChange={(e) => setDecision(e.target.value)}>
                    {DECISIONS.map((d) => <option key={d} value={d}>{d.replace(/_/g, " ")}</option>)}
                  </select>
                </div>
                <div className="form-field">
                  <label>Reviewer *</label>
                  <input type="text" value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="Your name" />
                </div>
                <div className="form-field">
                  <label>Notes</label>
                  <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} placeholder="Optional notes" />
                </div>
                {submitError && <div className="message error-message">{submitError}</div>}
                {submitResult && (
                  <div className="message info-message">
                    Decision <strong>{submitResult.decision}</strong> submitted by {submitResult.reviewer}.
                  </div>
                )}
                <button type="button" className="primary-button" onClick={handleSubmit} disabled={submitting}>
                  {submitting ? "Submitting..." : "Submit Review"}
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
