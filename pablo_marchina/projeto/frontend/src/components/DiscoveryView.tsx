import { useEffect, useState } from "react";
import type {
  DiscoveryRunRead,
  DiscoveryCandidateRead,
  DiscoverySourceRead,
} from "../api/types";
import {
  listDiscoverySources,
  listDiscoveryRuns,
  listDiscoveryCandidates,
  promoteDiscoveryCandidate,
  discoverManualSeed,
  discoverUrlList,
} from "../api/product";

interface DiscoveryViewProps {
  onPromoteToStartup: (startupId: string) => void;
  onSelectRun: (runId: string) => void;
}

export function DiscoveryView({ onPromoteToStartup, onSelectRun }: DiscoveryViewProps) {
  const [sources, setSources] = useState<DiscoverySourceRead[]>([]);
  const [runs, setRuns] = useState<DiscoveryRunRead[]>([]);
  const [candidates, setCandidates] = useState<DiscoveryCandidateRead[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [loadingCandidates, setLoadingCandidates] = useState(true);
  const [loadingSources, setLoadingSources] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [promotingId, setPromotingId] = useState<string | null>(null);
  const [promoteError, setPromoteError] = useState<string | null>(null);
  const [candidateFilter, setCandidateFilter] = useState<string>("");
  const [showSeed, setShowSeed] = useState(false);
  const [seedName, setSeedName] = useState("");
  const [seedWebsite, setSeedWebsite] = useState("");
  const [seedSector, setSeedSector] = useState("");
  const [seeding, setSeeding] = useState(false);
  const [seedError, setSeedError] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<string>("");

  async function load() {
    setLoadingRuns(true);
    setLoadingCandidates(true);
    setLoadingSources(true);
    setError(null);
    try {
      const [runsData, sourcesData] = await Promise.all([
        listDiscoveryRuns(),
        listDiscoverySources(),
      ]);
      setRuns(runsData.items);
      setSources(sourcesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingRuns(false);
      setLoadingSources(false);
    }
    try {
      const candData = await listDiscoveryCandidates(0, 100, {
        ...(sourceFilter ? { source_id: sourceFilter } : {}),
      });
      setCandidates(candData.items);
    } catch {
      // non-blocking
    } finally {
      setLoadingCandidates(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handlePromote(candidateId: string) {
    setPromotingId(candidateId);
    setPromoteError(null);
    try {
      const result = await promoteDiscoveryCandidate(candidateId);
      onPromoteToStartup(result.startup_id);
    } catch (err) {
      setPromoteError(err instanceof Error ? err.message : String(err));
    } finally {
      setPromotingId(null);
    }
  }

  async function handleManualSeed() {
    if (!seedName.trim() || !seedWebsite.trim() || !seedSector.trim()) {
      setSeedError("All fields are required.");
      return;
    }
    setSeeding(true);
    setSeedError(null);
    try {
      await discoverManualSeed({
        entries: [{
          name: seedName.trim(),
          website: seedWebsite.trim(),
          sector: seedSector.trim(),
        }],
      });
      setShowSeed(false);
      setSeedName("");
      setSeedWebsite("");
      setSeedSector("");
      await load();
    } catch (err) {
      setSeedError(err instanceof Error ? err.message : String(err));
    } finally {
      setSeeding(false);
    }
  }

  const filteredCandidates = candidateFilter
    ? candidates.filter((c) =>
        c.discovered_name.toLowerCase().includes(candidateFilter.toLowerCase()) ||
        c.sector?.toLowerCase().includes(candidateFilter.toLowerCase()),
      )
    : candidates;

  return (
    <div className="discovery-page">
      <div className="panel">
        <div className="panel-header">
          <h2>Discovery</h2>
          <div className="panel-header-actions">
            <button type="button" className="secondary-button" onClick={() => setShowSeed(!showSeed)}>
              {showSeed ? "Cancel" : "Manual Seed"}
            </button>
            <button type="button" className="secondary-button" onClick={load}>Refresh</button>
          </div>
        </div>

        {showSeed && (
          <div className="panel-body create-form">
            <h3>Manual Seed</h3>
            <div className="form-field">
              <label>Name *</label>
              <input type="text" value={seedName} onChange={(e) => setSeedName(e.target.value)} placeholder="Startup name" />
            </div>
            <div className="form-field">
              <label>Website *</label>
              <input type="url" value={seedWebsite} onChange={(e) => setSeedWebsite(e.target.value)} placeholder="https://example.com" />
            </div>
            <div className="form-field">
              <label>Sector *</label>
              <input type="text" value={seedSector} onChange={(e) => setSeedSector(e.target.value)} placeholder="HealthTech, FinTech, ..." />
            </div>
            {seedError && <div className="message error-message">{seedError}</div>}
            <button type="button" className="primary-button" onClick={handleManualSeed} disabled={seeding}>
              {seeding ? "Seeding..." : "Seed Discovery"}
            </button>
          </div>
        )}

        <div className="panel-body">
          {error && <div className="message error-message">{error}</div>}
          {promoteError && <div className="message warning-message">{promoteError}</div>}
        </div>
      </div>

      {loadingSources ? (
        <div className="panel"><div className="panel-body"><p className="loading-text">Loading sources...</p></div></div>
      ) : sources.length > 0 && (
        <div className="panel">
          <div className="panel-header"><h2>Sources</h2></div>
          <div className="panel-body">
            <table className="data-table">
              <thead>
                <tr><th>Name</th><th>Type</th><th>Scope</th><th>Status</th></tr>
              </thead>
              <tbody>
                {sources.map((s) => (
                  <tr key={s.source_id}>
                    <td><strong>{s.name}</strong></td>
                    <td>{s.source_type}</td>
                    <td>{s.country_scope} / {s.sector_scope}</td>
                    <td><span className={`badge ${s.usable ? "cap-ok" : "cap-off"}`}>{s.usable ? "Usable" : "Unavailable"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="panel">
        <div className="panel-header"><h2>Discovery Runs</h2></div>
        <div className="panel-body">
          {loadingRuns ? (
            <p className="loading-text">Loading runs...</p>
          ) : runs.length === 0 ? (
            <p className="empty-state">No discovery runs yet.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr><th>ID</th><th>Status</th><th>Candidates</th><th>Duplicates</th><th>Started</th></tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id}>
                    <td><code>{r.id.slice(0, 12)}...</code></td>
                    <td><span className={`badge status-${r.status}`}>{r.status}</span></td>
                    <td>{r.candidates_created}</td>
                    <td>{r.duplicates_found}</td>
                    <td>{r.started_at ? new Date(r.started_at).toLocaleString() : <span className="muted">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2>Candidates</h2>
          <div className="panel-header-actions">
            <input
              type="text"
              placeholder="Filter by name or sector..."
              value={candidateFilter}
              onChange={(e) => setCandidateFilter(e.target.value)}
              className="filter-input"
            />
            <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} className="filter-select">
              <option value="">All sources</option>
              {sources.map((s) => (
                <option key={s.source_id} value={s.source_id}>{s.name}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="panel-body">
          {loadingCandidates ? (
            <p className="loading-text">Loading candidates...</p>
          ) : filteredCandidates.length === 0 ? (
            <p className="empty-state">No candidates found.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr><th>Name</th><th>Sector</th><th>Confidence</th><th>Status</th><th>AI Native Signal</th><th></th></tr>
              </thead>
              <tbody>
                {filteredCandidates.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <strong>{c.discovered_name}</strong>
                      {c.normalized_name !== c.discovered_name && (
                        <span className="muted"> ({c.normalized_name})</span>
                      )}
                    </td>
                    <td>{c.sector}</td>
                    <td><span className={`badge ${c.confidence === "high" ? "cap-ok" : c.confidence === "medium" ? "cap-warn" : "cap-off"}`}>{c.confidence}</span></td>
                    <td><span className={`badge status-${c.status}`}>{c.status}</span></td>
                    <td>
                      {c.ai_native_signals_json &&
                      Object.keys(c.ai_native_signals_json).length > 0 ? (
                        <span className="badge cap-exp">Detected</span>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>
                      {c.status === "new" && (
                        <button
                          type="button"
                          className="link-button"
                          onClick={() => handlePromote(c.id)}
                          disabled={promotingId === c.id}
                        >
                          {promotingId === c.id ? "Promoting..." : "Promote to Startup"}
                        </button>
                      )}
                      {c.promoted_startup_id && (
                        <button
                          type="button"
                          className="link-button"
                          onClick={() => onPromoteToStartup(c.promoted_startup_id!)}
                        >
                          View Startup
                        </button>
                      )}
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