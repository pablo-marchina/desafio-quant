import { useEffect, useState } from "react";
import type { OpportunityListItem, RankedOpportunityRead } from "../api/types";
import { getQualityReport, listOpportunities, listRankedOpportunities } from "../api/product";

interface OpportunitiesViewProps {
  onSelectRun: (runId: string) => void;
  onSelectStartup: (startupId: string) => void;
}

type Tab = "all" | "ranked";

export function OpportunitiesView({ onSelectRun, onSelectStartup }: OpportunitiesViewProps) {
  const [tab, setTab] = useState<Tab>("all");
  const [opps, setOpps] = useState<OpportunityListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const [rankedOpps, setRankedOpps] = useState<RankedOpportunityRead[]>([]);
  const [rankedTotal, setRankedTotal] = useState(0);
  const [loadingRanked, setLoadingRanked] = useState(false);
  const [rankedError, setRankedError] = useState<string | null>(null);
  const [qualityThresholds, setQualityThresholds] = useState<Record<string, number>>({});

  function threshold(metric: string, fallback = 1): number {
    return qualityThresholds[metric] ?? fallback;
  }

  async function loadAll(pageOffset = 0) {
    setLoading(true);
    setError(null);
    try {
      const resp = await listOpportunities(pageOffset, limit);
      setOpps(resp.items);
      setTotal(resp.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function loadRanked(pageOffset = 0) {
    setLoadingRanked(true);
    setRankedError(null);
    try {
      const resp = await listRankedOpportunities(pageOffset, limit);
      setRankedOpps(resp.items);
      setRankedTotal(resp.total);
    } catch (err) {
      setRankedError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingRanked(false);
    }
  }

  useEffect(() => {
    getQualityReport()
      .then((report) => {
        const next: Record<string, number> = {};
        Object.entries(report.thresholds ?? {}).forEach(([metric, spec]) => {
          const thresholdValue = spec?.threshold;
          if (typeof thresholdValue === "number") next[metric] = thresholdValue;
        });
        setQualityThresholds(next);
      })
      .catch(() => setQualityThresholds({}));
  }, []);

  useEffect(() => {
    if (tab === "all") {
      loadAll(offset);
    } else {
      loadRanked(offset);
    }
  }, [tab, offset]);

  if (tab === "all" && loading) return <div className="panel"><div className="panel-body"><p className="loading-text">Loading opportunities...</p></div></div>;

  return (
    <div className="opportunities-page">
      <div className="panel">
        <div className="panel-header">
          <h2>Opportunities</h2>
          <div className="panel-header-actions">
            <div className="tab-row">
              <button
                type="button"
                className={`tab-btn ${tab === "all" ? "active" : ""}`}
                onClick={() => { setTab("all"); setOffset(0); }}
              >
                All
              </button>
              <button
                type="button"
                className={`tab-btn ${tab === "ranked" ? "active" : ""}`}
                onClick={() => { setTab("ranked"); setOffset(0); }}
              >
                Ranked
              </button>
            </div>
            <span className="muted">{tab === "all" ? total : rankedTotal} total</span>
            <button type="button" className="secondary-button" onClick={() => { if (tab === "all") loadAll(offset); else loadRanked(offset); }}>Refresh</button>
          </div>
        </div>

        <div className="panel-body">
          {tab === "all" && (
            <>
              {error && <div className="message error-message">{error}</div>}

              {!error && opps.length === 0 && (
                <p className="empty-state">No opportunities yet. Run analyses to generate them.</p>
              )}

              {opps.length > 0 && (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Startup</th>
                      <th>Composite Score</th>
                      <th>Motion</th>
                      <th>Activation Playbook</th>
                      <th>Evidence Coverage</th>
                      <th>Unsupported Claims</th>
                      <th>Export Ready</th>
                      <th>Review Ready</th>
                      <th>Dossier</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {opps.map((o) => (
                      <tr key={o.startup_id}>
                        <td>
                          <button
                            type="button"
                            className="link-button"
                            onClick={() => onSelectStartup(o.startup_id)}
                          >
                            {o.startup_name}
                          </button>
                        </td>
                        <td><strong>{o.composite_score?.toFixed(1) ?? "—"}</strong></td>
                        <td><span className="badge">{o.recommended_motion ?? "—"}</span></td>
                        <td>
                          {o.top_activation_playbook ? (
                            <span title={`Confidence: ${o.activation_confidence ?? "—"}`}>
                              {o.top_activation_playbook}
                            </span>
                          ) : <span className="muted">—</span>}
                        </td>
                        <td>{o.evidence_coverage != null ? `${Math.round(o.evidence_coverage * 100)}%` : "—"}</td>
                        <td>{o.unsupported_claim_count ?? "—"}</td>
                        <td>
                          <span className={`badge ${o.export_readiness_score != null && o.export_readiness_score >= threshold("export_readiness_score") ? "cap-ok" : "cap-warn"}`}>
                            {o.export_readiness_score != null ? o.export_readiness_score.toFixed(2) : "—"}
                          </span>
                        </td>
                        <td>
                          <span className={`badge ${o.review_readiness_score != null && o.review_readiness_score >= threshold("review_readiness_score") ? "cap-ok" : "cap-warn"}`}>
                            {o.review_readiness_score != null ? o.review_readiness_score.toFixed(2) : "—"}
                          </span>
                        </td>
                        <td>{o.dossier_available ? <span className="badge cap-ok">Yes</span> : <span className="muted">No</span>}</td>
                        <td>
                          {o.latest_analysis_run_id && (
                            <button
                              type="button"
                              className="link-button"
                              onClick={() => onSelectRun(o.latest_analysis_run_id!)}
                            >
                              View Run
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {total > limit && (
                <div className="pagination-row">
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - limit))}
                  >
                    Previous
                  </button>
                  <span className="muted">Page {Math.floor(offset / limit) + 1} of {Math.ceil(total / limit)}</span>
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={offset + limit >= total}
                    onClick={() => setOffset(offset + limit)}
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}

          {tab === "ranked" && (
            <>
              {rankedError && <div className="message error-message">{rankedError}</div>}

              {loadingRanked && <p className="loading-text">Loading ranked opportunities...</p>}

              {!loadingRanked && !rankedError && rankedOpps.length === 0 && (
                <p className="empty-state">No ranked opportunities yet. Compute opportunity scores first.</p>
              )}

              {!loadingRanked && rankedOpps.length > 0 && (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Startup</th>
                      <th>Sector</th>
                      <th>Score</th>
                      <th>Tier</th>
                      <th>Recommended Action</th>
                      <th>Evidence Count</th>
                      <th>Penalty Total</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {rankedOpps.map((ro) => (
                      <tr key={ro.startup_id}>
                        <td>
                          <button
                            type="button"
                            className="link-button"
                            onClick={() => onSelectStartup(ro.startup_id)}
                          >
                            {ro.startup_name}
                          </button>
                        </td>
                        <td>{ro.sector || <span className="muted">—</span>}</td>
                        <td><strong>{ro.opportunity_score?.toFixed(4)}</strong></td>
                        <td>
                          <span className={`badge ${ro.score_tier === "high" ? "cap-ok" : ro.score_tier === "medium" ? "cap-warn" : "cap-bad"}`}>
                            {ro.score_tier}
                          </span>
                        </td>
                        <td>{ro.recommended_action || <span className="muted">—</span>}</td>
                        <td>{ro.evidence_ref_count}</td>
                        <td className="text-warn">{ro.penalty_total?.toFixed(4) ?? "0"}</td>
                        <td>
                          <button
                            type="button"
                            className="link-button"
                            onClick={() => onSelectRun(ro.latest_analysis_run_id)}
                          >
                            View Run
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {rankedTotal > limit && (
                <div className="pagination-row">
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - limit))}
                  >
                    Previous
                  </button>
                  <span className="muted">Page {Math.floor(offset / limit) + 1} of {Math.ceil(rankedTotal / limit)}</span>
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={offset + limit >= rankedTotal}
                    onClick={() => setOffset(offset + limit)}
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
