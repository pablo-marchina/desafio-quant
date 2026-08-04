import { useEffect, useState } from "react";
import type { StartupRead } from "../api/types";
import { getStartup, updateStartup, runMainProductPipelineForStartup } from "../api/product";

interface StartupDetailPanelProps {
  startupId: string;
  onBack: () => void;
  onRunCreated: (runId: string) => void;
  onPipelineCreated?: (workflowId: string, analysisRunId: string | null) => void;
}

export function StartupDetailPanel({ startupId, onBack, onRunCreated, onPipelineCreated }: StartupDetailPanelProps) {
  const [startup, setStartup] = useState<StartupRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editWebsite, setEditWebsite] = useState("");
  const [editSector, setEditSector] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setStartup(await getStartup(startupId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [startupId]);

  function startEdit() {
    if (!startup) return;
    setEditName(startup.name);
    setEditWebsite(startup.website);
    setEditSector(startup.sector);
    setEditing(true);
    setEditError(null);
  }

  async function handleSave() {
    if (!editName.trim() || !editWebsite.trim() || !editSector.trim()) {
      setEditError("All fields are required.");
      return;
    }
    setSaving(true);
    setEditError(null);
    try {
      await updateStartup(startupId, {
        name: editName.trim(),
        website: editWebsite.trim(),
        sector: editSector.trim(),
      });
      setEditing(false);
      await load();
    } catch (err) {
      setEditError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleRunAnalysis() {
    setRunning(true);
    setRunError(null);
    try {
      const workflow = await runMainProductPipelineForStartup(startupId);
      if (onPipelineCreated) {
        onPipelineCreated(workflow.id, workflow.analysis_run_id);
      } else if (workflow.analysis_run_id) {
        onRunCreated(workflow.analysis_run_id);
      } else {
        throw new Error("Workflow queued, but this view cannot follow asynchronous execution.");
      }
    } catch (err) {
      setRunError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }

  if (loading) return <div className="panel"><div className="panel-body"><p className="loading-text">Loading startup...</p></div></div>;

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

  if (!startup) return null;

  return (
    <div className="startup-detail-page">
      <div className="panel">
        <div className="panel-header">
          <div className="panel-header-left">
            <button type="button" className="back-button" onClick={onBack}>← Back</button>
            <h2>{startup.name}</h2>
          </div>
          <button type="button" className="secondary-button" onClick={startEdit}>Edit</button>
        </div>

        {editing && (
          <div className="panel-body edit-section">
            <h3>Edit Startup</h3>
            <div className="form-field"><label>Name</label><input type="text" value={editName} onChange={(e) => setEditName(e.target.value)} /></div>
            <div className="form-field"><label>Website</label><input type="url" value={editWebsite} onChange={(e) => setEditWebsite(e.target.value)} /></div>
            <div className="form-field"><label>Sector</label><input type="text" value={editSector} onChange={(e) => setEditSector(e.target.value)} /></div>
            {editError && <div className="message error-message">{editError}</div>}
            <button type="button" className="primary-button" onClick={handleSave} disabled={saving}>{saving ? "Saving..." : "Save"}</button>
          </div>
        )}

        <div className="panel-body">
          <table className="data-table">
            <tbody>
              <tr><td className="label-cell">Normalized Name</td><td>{startup.normalized_name}</td></tr>
              <tr><td className="label-cell">Website</td><td className="url-cell">{startup.website}</td></tr>
              <tr><td className="label-cell">Country</td><td>{startup.country}</td></tr>
              <tr><td className="label-cell">Sector</td><td>{startup.sector}</td></tr>
              <tr><td className="label-cell">Status</td><td><span className={`badge status-${startup.status}`}>{startup.status}</span></td></tr>
              <tr><td className="label-cell">Description</td><td>{startup.description || <span className="muted">—</span>}</td></tr>
              <tr><td className="label-cell">Product Summary</td><td>{startup.product_summary || <span className="muted">—</span>}</td></tr>
              <tr><td className="label-cell">Tags</td><td>{startup.tags.length > 0 ? startup.tags.join(", ") : <span className="muted">—</span>}</td></tr>
              <tr><td className="label-cell">Evidence</td><td>{startup.evidence.length} items</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header"><h2>Analysis</h2></div>
        <div className="panel-body">
          {runError && <div className="message error-message">{runError}</div>}
          <button type="button" className="primary-button" onClick={handleRunAnalysis} disabled={running}>
            {running ? "Queueing Main Pipeline..." : "Run Main Pipeline"}
          </button>
        </div>
      </div>
    </div>
  );
}
