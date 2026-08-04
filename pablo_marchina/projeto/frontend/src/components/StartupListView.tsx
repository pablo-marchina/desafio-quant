import { useEffect, useState } from "react";
import type { StartupListItem, StartupCreatePayload } from "../api/types";
import { listStartups, createStartup } from "../api/product";

interface StartupListViewProps {
  onSelectStartup: (id: string) => void;
}

export function StartupListView({ onSelectStartup }: StartupListViewProps) {
  const [startups, setStartups] = useState<StartupListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createWebsite, setCreateWebsite] = useState("");
  const [createSector, setCreateSector] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setStartups(await listStartups());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleCreate() {
    if (!createName.trim() || !createWebsite.trim() || !createSector.trim()) {
      setCreateError("All fields are required.");
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const payload: StartupCreatePayload = {
        name: createName.trim(),
        website: createWebsite.trim(),
        sector: createSector.trim(),
      };
      await createStartup(payload);
      setCreateName("");
      setCreateWebsite("");
      setCreateSector("");
      setShowCreate(false);
      await load();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : String(err));
    } finally {
      setCreating(false);
    }
  }

  if (loading) return <div className="panel"><div className="panel-body"><p className="loading-text">Loading startups...</p></div></div>;

  return (
    <div className="startup-list-page">
      <div className="panel">
        <div className="panel-header">
          <h2>Startups</h2>
          <div className="panel-header-actions">
            <button type="button" className="secondary-button" onClick={load}>Refresh</button>
            <button type="button" className="primary-button-sm" onClick={() => setShowCreate(!showCreate)}>
              {showCreate ? "Cancel" : "New Startup"}
            </button>
          </div>
        </div>

        {showCreate && (
          <div className="panel-body create-form">
            <h3>Create Startup</h3>
            <div className="form-field">
              <label htmlFor="startup-name">Name *</label>
              <input
                id="startup-name"
                name="name"
                type="text"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                placeholder="Startup name"
              />
            </div>
            <div className="form-field">
              <label htmlFor="startup-website">Website *</label>
              <input
                id="startup-website"
                name="website"
                type="url"
                value={createWebsite}
                onChange={(e) => setCreateWebsite(e.target.value)}
                placeholder="https://example.com"
              />
            </div>
            <div className="form-field">
              <label htmlFor="startup-sector">Sector *</label>
              <input
                id="startup-sector"
                name="sector"
                type="text"
                value={createSector}
                onChange={(e) => setCreateSector(e.target.value)}
                placeholder="HealthTech, FinTech, ..."
              />
            </div>
            {createError && <div className="message error-message">{createError}</div>}
            <button
              type="button"
              className="primary-button"
              onClick={handleCreate}
              disabled={creating}
            >
              {creating ? "Creating..." : "Create Startup"}
            </button>
          </div>
        )}

        <div className="panel-body">
          {error && <div className="message error-message">{error}</div>}

          {!error && startups.length === 0 && (
            <p className="empty-state">No startups yet. Create one to get started.</p>
          )}

          {startups.length > 0 && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Sector</th>
                  <th>Website</th>
                  <th>Status</th>
                  <th>Last Analysis</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {startups.map((s) => (
                  <tr key={s.id}>
                    <td><strong>{s.name}</strong></td>
                    <td>{s.sector}</td>
                    <td className="url-cell">{s.website}</td>
                    <td><span className={`badge status-${s.status}`}>{s.status}</span></td>
                    <td>
                      {s.latest_analysis_status ? (
                        <span className={`badge status-${s.latest_analysis_status}`}>
                          {s.latest_analysis_status}
                        </span>
                      ) : (
                        <span className="muted">None</span>
                      )}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="link-button"
                        onClick={() => onSelectStartup(s.id)}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
