import { useEffect, useState } from "react";
import type { ProductWorkflowRunRead } from "../api/types";
import { listWorkflowRuns, getWorkflowRun, createWorkflowRun } from "../api/product";
import { WorkflowNodeTimeline } from "./WorkflowNodeTimeline";

interface WorkflowViewProps {
  onSelectWorkflowRun: (workflowId: string) => void;
  selectedWorkflowRunId: string | null;
  onSelectStartup: (startupId: string) => void;
  onViewFinalResult: (workflowId: string) => void;
}

export function WorkflowView({
  onSelectWorkflowRun,
  selectedWorkflowRunId,
  onSelectStartup,
  onViewFinalResult,
}: WorkflowViewProps) {
  const [runs, setRuns] = useState<ProductWorkflowRunRead[]>([]);
  const [selectedRun, setSelectedRun] = useState<ProductWorkflowRunRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [startupIdInput, setStartupIdInput] = useState("");
  const [creating, setCreating] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const resp = await listWorkflowRuns();
      setRuns(resp.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (selectedWorkflowRunId) {
      setLoadingDetail(true);
      setDetailError(null);
      getWorkflowRun(selectedWorkflowRunId)
        .then(setSelectedRun)
        .catch((err) => setDetailError(err instanceof Error ? err.message : String(err)))
        .finally(() => setLoadingDetail(false));
    }
  }, [selectedWorkflowRunId]);

  function handleSelectRun(runId: string) {
    onSelectWorkflowRun(runId);
  }

  async function handleCreateWorkflow() {
    const startupId = startupIdInput.trim();
    if (!startupId) {
      setError("Provide a startup_id to start the single product pipeline.");
      return;
    }
    setCreating(true);
    setError(null);
    try {
      const created = await createWorkflowRun({ startup_id: startupId, use_rag: true });
      setRuns((prev) => [created, ...prev]);
      onSelectWorkflowRun(created.id);
      setSelectedRun(created);
      onViewFinalResult(created.id);
      setStartupIdInput("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="workflow-page">
      <div className="panel">
        <div className="panel-header">
          <h2>Workflow Runs</h2>
          <div className="panel-header-actions">
            <button type="button" className="secondary-button" onClick={load}>Refresh</button>
          </div>
        </div>
        <div className="panel-body">
          <div className="form-grid compact-form-grid">
            <label>
              <span>Startup ID</span>
              <input
                value={startupIdInput}
                onChange={(e) => setStartupIdInput(e.target.value)}
                placeholder="startup_id"
              />
            </label>
            <div className="form-actions-inline">
              <button type="button" className="primary-button" onClick={handleCreateWorkflow} disabled={creating}>
                {creating ? "Starting..." : "Start Main Pipeline"}
              </button>
            </div>
          </div>
          {loading ? (
            <p className="loading-text">Loading workflow runs...</p>
          ) : error ? (
            <div className="message error-message">{error}</div>
          ) : runs.length === 0 ? (
            <p className="empty-state">No workflow runs yet. Create one from a startup detail or discovery candidate.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Status</th>
                  <th>Current Node</th>
                  <th>Graph Version</th>
                  <th>Startup</th>
                  <th>Started</th>
                  <th></th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id}>
                    <td><code>{r.id.slice(0, 12)}...</code></td>
                    <td><span className={`badge status-${r.status}`}>{r.status}</span></td>
                    <td>{r.current_node}</td>
                    <td>{r.graph_version}</td>
                    <td>
                      {r.startup_id ? (
                        <button
                          type="button"
                          className="link-button"
                          onClick={() => onSelectStartup(r.startup_id!)}
                        >
                          View
                        </button>
                      ) : <span className="muted">—</span>}
                    </td>
                    <td>{r.started_at ? new Date(r.started_at).toLocaleString() : <span className="muted">—</span>}</td>
                    <td>
                      <button
                        type="button"
                        className="link-button"
                        onClick={() => handleSelectRun(r.id)}
                      >
                        Details
                      </button>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="link-button"
                        onClick={() => onViewFinalResult(r.id)}
                      >
                        Final Result
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {loadingDetail && (
        <div className="panel"><div className="panel-body"><p className="loading-text">Loading workflow detail...</p></div></div>
      )}

      {detailError && (
        <div className="panel">
          <div className="panel-body">
            <div className="message error-message">{detailError}</div>
          </div>
        </div>
      )}

      {selectedRun && !loadingDetail && (
        <>
          <div className="panel">
            <div className="panel-header">
              <div className="panel-header-left">
                <button
                  type="button"
                  className="back-button"
                  onClick={() => { setSelectedRun(null); onSelectWorkflowRun(""); }}
                >
                  ← Back
                </button>
                <h2>Workflow Detail</h2>
              </div>
            </div>
            <div className="panel-body">
              <table className="data-table">
                <tbody>
                  <tr><td className="label-cell">ID</td><td><code>{selectedRun.id}</code></td></tr>
                  <tr><td className="label-cell">Status</td><td><span className={`badge status-${selectedRun.status}`}>{selectedRun.status}</span></td></tr>
                  <tr><td className="label-cell">Current Node</td><td>{selectedRun.current_node}</td></tr>
                  <tr><td className="label-cell">Graph Version</td><td>{selectedRun.graph_version}</td></tr>
                  {selectedRun.error_message && (
                    <tr><td className="label-cell">Error</td><td className="text-error">{selectedRun.error_message}</td></tr>
                  )}
                  {selectedRun.degraded_reason && (
                    <tr><td className="label-cell">Degraded Reason</td><td className="text-warn">{selectedRun.degraded_reason}</td></tr>
                  )}
                  <tr><td className="label-cell">Started</td><td>{selectedRun.started_at ? new Date(selectedRun.started_at).toLocaleString() : <span className="muted">—</span>}</td></tr>
                  <tr><td className="label-cell">Completed</td><td>{selectedRun.completed_at ? new Date(selectedRun.completed_at).toLocaleString() : <span className="muted">—</span>}</td></tr>
                  {selectedRun.startup_id && (
                    <tr><td className="label-cell">Startup</td><td><button type="button" className="link-button" onClick={() => onSelectStartup(selectedRun.startup_id!)}>View Startup</button></td></tr>
                  )}
                  <tr><td className="label-cell">Final Product Result</td><td><button type="button" className="secondary-button" onClick={() => onViewFinalResult(selectedRun.id)}>Open Complete Result</button></td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel">
            <div className="panel-header"><h2>Node Timeline</h2></div>
            <div className="panel-body">
              <WorkflowNodeTimeline
                nodes={selectedRun.nodes}
                currentNode={selectedRun.current_node}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}