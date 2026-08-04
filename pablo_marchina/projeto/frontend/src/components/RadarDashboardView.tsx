import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  JsonValue,
  RadarDashboardItem,
  RadarPopulateResponse,
} from "../api/types";
import { getRadarDashboard, populateRadarDashboard } from "../api/product";
import "./radar-dashboard.css";

interface RadarDashboardViewProps {
  onSelectStartup: (startupId: string) => void;
  onSelectRun: (runId: string) => void;
}

type ActiveTab = "companies" | "discovery" | "blockers" | "rejected";
type StatusFilter = "all" | "ready" | "analyzed" | "pending" | "attention";
type SortOption = "score" | "evidence" | "sources" | "name";

const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;
const SOURCE_LIMIT_OPTIONS = [0, 2, 4, 6] as const;
const PIPELINE_LIMIT_OPTIONS = [1, 3, 5, 10] as const;

function formatScore(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(1)
    : "—";
}

function normalizedRatio(value: number | null | undefined): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return Math.max(0, Math.min(1, value > 1 ? value / 100 : value));
}

function formatCoverage(value: number | null | undefined): string {
  const ratio = normalizedRatio(value);
  return ratio === null ? "—" : `${Math.round(ratio * 100)}%`;
}

function shortList(values: string[], limit = 3): string {
  if (!values.length) return "—";
  const visible = values.slice(0, limit);
  const remaining = values.length - visible.length;
  return remaining > 0
    ? `${visible.join(", ")} +${remaining}`
    : visible.join(", ");
}

function asRecord(value: JsonValue | undefined): Record<string, JsonValue> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value;
  }
  return {};
}

function stringValue(value: JsonValue | undefined): string {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}

function describeInformation(item: RadarDashboardItem): string {
  const info = item.information;
  const preferredKeys = [
    "description",
    "product_summary",
    "executive_summary",
    "reasoning",
  ];
  for (const key of preferredKeys) {
    const value = stringValue(info[key]);
    if (value) return value;
  }
  const scores = asRecord(info.scores);
  const scoreKeys = Object.keys(scores);
  if (scoreKeys.length > 0) return `Scores: ${scoreKeys.join(", ")}`;
  return "Runtime artifacts available in the audit details.";
}

function isReady(item: RadarDashboardItem): boolean {
  return (
    item.recommendation_status?.toLowerCase() === "ready" ||
    item.activation_recommendations.length > 0
  );
}

function isAnalyzed(item: RadarDashboardItem): boolean {
  return Boolean(item.analysis_run_id) || item.row_type === "analyzed_startup";
}

function needsAttention(item: RadarDashboardItem): boolean {
  const status = `${item.analysis_status ?? ""} ${item.recommendation_status ?? ""}`.toLowerCase();
  return (
    status.includes("fail") ||
    status.includes("degrad") ||
    status.includes("block") ||
    (item.unsupported_claim_count ?? 0) > 0
  );
}

function countFailures(response: RadarPopulateResponse | null): number {
  if (!response) return 0;
  return (
    response.discovery_results.filter((item) => {
      const status = stringValue(item.status).toLowerCase();
      return status === "failed" || status === "degraded";
    }).length +
    response.promoted_candidates.filter((item) => {
      const status = stringValue(item.status).toLowerCase();
      return status === "failed" || status === "degraded";
    }).length +
    response.pipeline_results.filter((item) => item.status === "failed").length
  );
}

function safeExternalUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:"
      ? url.toString()
      : null;
  } catch {
    return null;
  }
}

function scoreTier(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "No score";
  if (value >= 80) return "80–100";
  if (value >= 60) return "60–79";
  if (value >= 40) return "40–59";
  return "0–39";
}

function runtimeItemTitle(item: Record<string, JsonValue>, index: number): string {
  const keys = [
    "company_name",
    "discovered_name",
    "name",
    "source_id",
    "startup_id",
    "candidate_id",
  ];
  for (const key of keys) {
    const value = stringValue(item[key]);
    if (value) return value;
  }
  return `Item ${index + 1}`;
}

function runtimeItemStatus(item: Record<string, JsonValue>): string {
  return stringValue(item.status) || stringValue(item.reason) || "recorded";
}

function runtimeItemDetail(item: Record<string, JsonValue>): string {
  for (const key of ["error", "error_message", "degraded_reason", "current_node"]) {
    const value = stringValue(item[key]);
    if (value) return value;
  }
  const artifactErrors = item.artifact_errors;
  if (Array.isArray(artifactErrors)) {
    const values = artifactErrors.map((value) => stringValue(value)).filter(Boolean);
    if (values.length > 0) return values.join("; ");
  }
  return runtimeItemStatus(item);
}

function RuntimeRecordList({
  title,
  description,
  items,
  emptyMessage,
}: {
  title: string;
  description: string;
  items: Record<string, JsonValue>[];
  emptyMessage: string;
}) {
  return (
    <section className="radar-runtime-section" aria-labelledby={`${title}-heading`}>
      <div className="radar-section-heading">
        <div>
          <p className="eyebrow">Runtime evidence</p>
          <h3 id={`${title}-heading`}>{title}</h3>
          <p className="muted">{description}</p>
        </div>
        <span className="radar-count-badge">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <p className="empty-state">{emptyMessage}</p>
      ) : (
        <div className="radar-runtime-list">
          {items.map((item, index) => (
            <details className="radar-runtime-card" key={`${runtimeItemTitle(item, index)}-${index}`}>
              <summary>
                <span>
                  <strong>{runtimeItemTitle(item, index)}</strong>
                  <small>{runtimeItemDetail(item)}</small>
                </span>
                <span className={`badge status-${runtimeItemStatus(item).toLowerCase()}`}>
                  {runtimeItemStatus(item)}
                </span>
              </summary>
              <pre className="json-block compact-json-block">{JSON.stringify(item, null, 2)}</pre>
            </details>
          ))}
        </div>
      )}
    </section>
  );
}

function DistributionBars({
  title,
  entries,
}: {
  title: string;
  entries: { label: string; value: number }[];
}) {
  const maxValue = Math.max(1, ...entries.map((entry) => entry.value));
  return (
    <section className="radar-distribution-card">
      <h3>{title}</h3>
      <div className="radar-distribution-list">
        {entries.map((entry) => (
          <div className="radar-distribution-row" key={entry.label}>
            <span>{entry.label}</span>
            <div className="radar-distribution-track" aria-hidden="true">
              <span style={{ width: `${(entry.value / maxValue) * 100}%` }} />
            </div>
            <strong>{entry.value}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

export function RadarDashboardView({ onSelectStartup, onSelectRun }: RadarDashboardViewProps) {
  const [items, setItems] = useState<RadarDashboardItem[]>([]);
  const [total, setTotal] = useState(0);
  const [analyzedTotal, setAnalyzedTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [populating, setPopulating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [populateResult, setPopulateResult] = useState<RadarPopulateResponse | null>(null);
  const [runPipeline, setRunPipeline] = useState(true);
  const [forceRerun, setForceRerun] = useState(false);
  const [sourceLimit, setSourceLimit] = useState<number>(2);
  const [pipelineLimit, setPipelineLimit] = useState<number>(5);
  const [activeTab, setActiveTab] = useState<ActiveTab>("companies");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sectorFilter, setSectorFilter] = useState("all");
  const [sortOption, setSortOption] = useState<SortOption>("score");
  const [pageSize, setPageSize] = useState<number>(20);
  const [page, setPage] = useState(1);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const limit = 100;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getRadarDashboard(limit);
      setItems(response.items);
      setTotal(response.total);
      setAnalyzedTotal(response.analyzed_total);
      setUpdatedAt(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const populate = useCallback(async () => {
    setPopulating(true);
    setError(null);
    try {
      const response = await populateRadarDashboard(
        limit,
        sourceLimit,
        pipelineLimit,
        runPipeline,
        forceRerun,
      );
      setPopulateResult(response);
      setItems(response.dashboard.items);
      setTotal(response.dashboard.total);
      setAnalyzedTotal(response.dashboard.analyzed_total);
      setUpdatedAt(new Date());
      setPage(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPopulating(false);
    }
  }, [forceRerun, pipelineLimit, runPipeline, sourceLimit]);

  useEffect(() => {
    void load();
  }, [load]);

  const analyzedCount = useMemo(() => items.filter(isAnalyzed).length, [items]);
  const recommendationReadyCount = useMemo(() => items.filter(isReady).length, [items]);
  const attentionCount = useMemo(() => items.filter(needsAttention).length, [items]);
  const averageEvidence = useMemo(() => {
    const values = items
      .map((item) => normalizedRatio(item.evidence_coverage))
      .filter((value): value is number => value !== null);
    if (values.length === 0) return null;
    return values.reduce((sum, value) => sum + value, 0) / values.length;
  }, [items]);

  const failureCount = countFailures(populateResult);
  const discoveryQueue = populateResult?.discovery_queue ?? [];
  const rejectedEntities = populateResult?.rejected_entities ?? [];
  const blockerRecords = useMemo<Record<string, JsonValue>[]>(() => {
    if (!populateResult) return [];
    const discovery = populateResult.discovery_results.filter((item) => {
      const status = stringValue(item.status).toLowerCase();
      return status === "failed" || status === "degraded";
    });
    const promotions = populateResult.promoted_candidates.filter((item) => {
      const status = stringValue(item.status).toLowerCase();
      return status === "failed" || status === "degraded";
    });
    const pipelines = populateResult.pipeline_results
      .filter((item) => item.status === "failed")
      .map((item) => item as unknown as Record<string, JsonValue>);
    return [...discovery, ...promotions, ...pipelines];
  }, [populateResult]);

  const sectors = useMemo(
    () =>
      Array.from(
        new Set(
          items
            .map((item) => item.sector?.trim())
            .filter((sector): sector is string => Boolean(sector)),
        ),
      ).sort((a, b) => a.localeCompare(b, "pt-BR")),
    [items],
  );

  const filteredItems = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("pt-BR");
    const filtered = items.filter((item) => {
      const matchesSearch =
        !query ||
        [
          item.company_name,
          item.sector,
          item.country,
          item.website,
          item.recommended_motion,
          ...item.top_gaps,
          ...item.top_nvidia_technologies,
        ]
          .filter(Boolean)
          .some((value) => String(value).toLocaleLowerCase("pt-BR").includes(query));
      const matchesSector = sectorFilter === "all" || item.sector === sectorFilter;
      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "ready" && isReady(item)) ||
        (statusFilter === "analyzed" && isAnalyzed(item)) ||
        (statusFilter === "pending" && !isAnalyzed(item)) ||
        (statusFilter === "attention" && needsAttention(item));
      return matchesSearch && matchesSector && matchesStatus;
    });

    return [...filtered].sort((a, b) => {
      if (sortOption === "name") return a.company_name.localeCompare(b.company_name, "pt-BR");
      if (sortOption === "evidence") {
        return (normalizedRatio(b.evidence_coverage) ?? -1) - (normalizedRatio(a.evidence_coverage) ?? -1);
      }
      if (sortOption === "sources") return b.source_count - a.source_count;
      return (b.opportunity_score ?? -1) - (a.opportunity_score ?? -1);
    });
  }, [items, search, sectorFilter, sortOption, statusFilter]);

  useEffect(() => {
    setPage(1);
  }, [pageSize, search, sectorFilter, sortOption, statusFilter]);

  const pageCount = Math.max(1, Math.ceil(filteredItems.length / pageSize));
  useEffect(() => {
    setPage((current) => Math.min(current, pageCount));
  }, [pageCount]);

  const paginatedItems = useMemo(
    () => filteredItems.slice((page - 1) * pageSize, page * pageSize),
    [filteredItems, page, pageSize],
  );

  const statusDistribution = useMemo(
    () => [
      { label: "Ready", value: recommendationReadyCount },
      { label: "Analyzed", value: analyzedCount },
      { label: "Pending", value: Math.max(0, items.length - analyzedCount) },
      { label: "Attention", value: attentionCount },
    ],
    [analyzedCount, attentionCount, items.length, recommendationReadyCount],
  );

  const scoreDistribution = useMemo(() => {
    const labels = ["80–100", "60–79", "40–59", "0–39", "No score"];
    const counts = new Map(labels.map((label) => [label, 0]));
    items.forEach((item) => {
      const tier = scoreTier(item.opportunity_score);
      counts.set(tier, (counts.get(tier) ?? 0) + 1);
    });
    return labels.map((label) => ({ label, value: counts.get(label) ?? 0 }));
  }, [items]);

  if (loading) {
    return (
      <div className="panel radar-loading-panel" role="status" aria-live="polite">
        <div className="panel-body">
          <p className="eyebrow">Unified runtime pipeline</p>
          <h2>Loading Radar Dashboard</h2>
          <div className="radar-skeleton-grid" aria-hidden="true">
            <span /><span /><span /><span /><span />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="radar-dashboard-page">
      <section className="panel radar-hero-panel">
        <div className="panel-header radar-dashboard-header">
          <div>
            <p className="eyebrow">Unified runtime pipeline</p>
            <h2>Radar Dashboard</h2>
            <p className="muted radar-header-copy">
              Decision-first portfolio view with explicit evidence, NVIDIA opportunity,
              recommendations and central-pipeline blockers.
            </p>
            {updatedAt && (
              <small className="radar-updated-at">
                Refreshed {updatedAt.toLocaleString("pt-BR")}
              </small>
            )}
          </div>
          <div className="radar-run-controls">
            <label className="toggle-row">
              <input
                type="checkbox"
                checked={runPipeline}
                onChange={(event) => setRunPipeline(event.target.checked)}
              />
              Run full analysis
            </label>
            <label className="toggle-row">
              <input
                type="checkbox"
                checked={forceRerun}
                onChange={(event) => setForceRerun(event.target.checked)}
              />
              Force rerun
            </label>
            <label className="radar-inline-field">
              Discovery sources
              <select
                value={sourceLimit}
                onChange={(event) => setSourceLimit(Number(event.target.value))}
              >
                {SOURCE_LIMIT_OPTIONS.map((option) => (
                  <option value={option} key={option}>{option}</option>
                ))}
              </select>
            </label>
            <label className="radar-inline-field">
              Companies analyzed per run
              <select
                value={pipelineLimit}
                onChange={(event) => setPipelineLimit(Number(event.target.value))}
              >
                {PIPELINE_LIMIT_OPTIONS.map((option) => (
                  <option value={option} key={option}>{option}</option>
                ))}
              </select>
            </label>
            <div className="radar-action-row">
              <button type="button" className="secondary-button" onClick={() => void load()} disabled={populating}>
                Refresh
              </button>
              <button type="button" className="primary-button-sm" onClick={() => void populate()} disabled={populating}>
                {populating ? "Running central pipeline…" : "Populate Dashboard"}
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div className="message error-message" role="alert">
            <strong>Dashboard request failed.</strong> {error}
          </div>
        )}
        {populateResult && !error && (
          <div className="message radar-run-summary" role="status">
            <strong>{populateResult.status}</strong>
            <span>{populateResult.message}</span>
          </div>
        )}

        <div className="radar-kpi-grid panel-body">
          <article className="score-card primary-score">
            <span>Companies available</span>
            <strong>{total}</strong>
            <small>{items.length} loaded in this view</small>
          </article>
          <article className="score-card">
            <span>Analyzed companies</span>
            <strong>{analyzedCount}/{analyzedTotal}</strong>
            <small>{items.length ? Math.round((analyzedCount / items.length) * 100) : 0}% of loaded companies</small>
          </article>
          <article className="score-card">
            <span>Ready recommendations</span>
            <strong>{recommendationReadyCount}</strong>
            <small>Evidence-backed activation output</small>
          </article>
          <article className="score-card">
            <span>Average evidence</span>
            <strong>{formatCoverage(averageEvidence)}</strong>
            <small>Across rows with measured coverage</small>
          </article>
          <article className={`score-card ${failureCount || attentionCount ? "radar-attention-card" : ""}`}>
            <span>Runtime attention</span>
            <strong>{failureCount || attentionCount}</strong>
            <small>{failureCount ? `${failureCount} blockers in latest populate` : `${attentionCount} rows need review`}</small>
          </article>
        </div>

        <div className="radar-chart-grid panel-body">
          <DistributionBars title="Portfolio state" entries={statusDistribution} />
          <DistributionBars title="Opportunity score distribution" entries={scoreDistribution} />
        </div>
      </section>

      <section className="panel radar-data-panel">
        <div className="radar-tab-row" role="tablist" aria-label="Radar output sections">
          <button type="button" role="tab" aria-selected={activeTab === "companies"} className={activeTab === "companies" ? "active" : ""} onClick={() => setActiveTab("companies")}>
            Decision table <span>{items.length}</span>
          </button>
          <button type="button" role="tab" aria-selected={activeTab === "discovery"} className={activeTab === "discovery" ? "active" : ""} onClick={() => setActiveTab("discovery")}>
            Discovery queue <span>{discoveryQueue.length}</span>
          </button>
          <button type="button" role="tab" aria-selected={activeTab === "blockers"} className={activeTab === "blockers" ? "active" : ""} onClick={() => setActiveTab("blockers")}>
            Runtime blockers <span>{failureCount}</span>
          </button>
          <button type="button" role="tab" aria-selected={activeTab === "rejected"} className={activeTab === "rejected" ? "active" : ""} onClick={() => setActiveTab("rejected")}>
            Rejected entities <span>{rejectedEntities.length}</span>
          </button>
        </div>

        {activeTab === "companies" && (
          <>
            <div className="radar-filter-bar panel-body">
              <label className="radar-search-field">
                <span>Search portfolio</span>
                <input
                  type="search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Company, sector, gap or NVIDIA technology"
                />
              </label>
              <label>
                <span>Status</span>
                <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}>
                  <option value="all">All statuses</option>
                  <option value="ready">Recommendation ready</option>
                  <option value="analyzed">Analyzed</option>
                  <option value="pending">Pending analysis</option>
                  <option value="attention">Needs attention</option>
                </select>
              </label>
              <label>
                <span>Sector</span>
                <select value={sectorFilter} onChange={(event) => setSectorFilter(event.target.value)}>
                  <option value="all">All sectors</option>
                  {sectors.map((sector) => <option value={sector} key={sector}>{sector}</option>)}
                </select>
              </label>
              <label>
                <span>Sort</span>
                <select value={sortOption} onChange={(event) => setSortOption(event.target.value as SortOption)}>
                  <option value="score">Opportunity score</option>
                  <option value="evidence">Evidence coverage</option>
                  <option value="sources">Source count</option>
                  <option value="name">Company name</option>
                </select>
              </label>
              <label>
                <span>Rows</span>
                <select value={pageSize} onChange={(event) => setPageSize(Number(event.target.value))}>
                  {PAGE_SIZE_OPTIONS.map((option) => <option value={option} key={option}>{option}</option>)}
                </select>
              </label>
            </div>

            <div className="radar-results-summary panel-body">
              <span><strong>{filteredItems.length}</strong> matching companies</span>
              {(search || statusFilter !== "all" || sectorFilter !== "all") && (
                <button
                  type="button"
                  className="link-button"
                  onClick={() => {
                    setSearch("");
                    setStatusFilter("all");
                    setSectorFilter("all");
                  }}
                >
                  Clear filters
                </button>
              )}
            </div>

            {!error && filteredItems.length === 0 ? (
              <p className="empty-state">
                {items.length === 0
                  ? "No companies are available yet. Populate the dashboard to execute discovery, promotion, analysis, recommendation, scoring and dossier generation through the central runtime path."
                  : "No companies match the current filters."}
              </p>
            ) : (
              <div className="table-wrap radar-table-wrap">
                <table className="data-table radar-decision-table">
                  <thead>
                    <tr>
                      <th>Company</th>
                      <th>Decision</th>
                      <th>Evidence</th>
                      <th>NVIDIA opportunity</th>
                      <th>Top recommendation</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedItems.map((item) => {
                      const topRecommendation = item.activation_recommendations[0];
                      const website = safeExternalUrl(item.website);
                      return (
                        <tr key={`${item.row_type}-${item.startup_id ?? item.candidate_id ?? item.company_name}`}>
                          <td className="radar-company-cell">
                            <strong>{item.company_name}</strong>
                            <span>{item.sector || "Unknown sector"}{item.country ? ` · ${item.country}` : ""}</span>
                            {website && (
                              <a href={website} target="_blank" rel="noreferrer" className="radar-website-link">
                                {new URL(website).hostname}
                              </a>
                            )}
                            <details className="radar-row-details">
                              <summary>Information collected</summary>
                              <p>{describeInformation(item)}</p>
                              <pre className="json-block compact-json-block">{JSON.stringify(item.information, null, 2)}</pre>
                            </details>
                          </td>
                          <td>
                            <div className="radar-score-line">
                              <strong>{formatScore(item.opportunity_score)}</strong>
                              <span className={`badge tier-${(item.score_tier ?? "unscored").toLowerCase()}`}>
                                {item.score_tier ?? "unscored"}
                              </span>
                            </div>
                            <span className={`badge status-${(item.analysis_status ?? "unknown").toLowerCase()}`}>
                              {item.analysis_status ?? item.row_type}
                            </span>
                            <span className="radar-motion">{item.recommended_motion ?? "No decision generated"}</span>
                          </td>
                          <td>
                            <strong>{formatCoverage(item.evidence_coverage)}</strong>
                            <span>{item.source_count} sources</span>
                            <span className={(item.unsupported_claim_count ?? 0) > 0 ? "radar-warning-text" : "muted"}>
                              {item.unsupported_claim_count ?? "—"} unsupported claims
                            </span>
                          </td>
                          <td>
                            <strong>{shortList(item.top_nvidia_technologies, 3)}</strong>
                            <span>{shortList(item.top_gaps, 3)}</span>
                          </td>
                          <td className="radar-recommendation-cell">
                            {topRecommendation ? (
                              <>
                                <strong>{topRecommendation.playbook_name ?? topRecommendation.recommended_motion ?? "Recommendation"}</strong>
                                <span>{shortList(topRecommendation.nvidia_technologies, 3)}</span>
                                {topRecommendation.next_step && <p>{topRecommendation.next_step}</p>}
                                {item.activation_recommendations.length > 1 && (
                                  <details className="radar-row-details">
                                    <summary>{item.activation_recommendations.length - 1} more recommendations</summary>
                                    <ul className="stack-list compact-stack-list">
                                      {item.activation_recommendations.slice(1).map((recommendation, index) => (
                                        <li key={`${item.company_name}-${recommendation.playbook_name ?? recommendation.recommended_motion ?? index}`}>
                                          <strong>{recommendation.playbook_name ?? recommendation.recommended_motion ?? `Recommendation ${index + 2}`}</strong>
                                          <span>{shortList(recommendation.nvidia_technologies, 3)}</span>
                                          {recommendation.next_step && <span>{recommendation.next_step}</span>}
                                        </li>
                                      ))}
                                    </ul>
                                  </details>
                                )}
                              </>
                            ) : (
                              <span className="muted">Not generated yet</span>
                            )}
                          </td>
                          <td>
                            <div className="radar-row-actions">
                              {item.startup_id && (
                                <button type="button" className="secondary-button" onClick={() => onSelectStartup(item.startup_id!)}>
                                  Startup
                                </button>
                              )}
                              {item.analysis_run_id && (
                                <button type="button" className="primary-button-sm" onClick={() => onSelectRun(item.analysis_run_id!)}>
                                  Open result
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {filteredItems.length > 0 && (
              <nav className="radar-pagination panel-body" aria-label="Dashboard table pagination">
                <button type="button" className="secondary-button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page === 1}>
                  Previous
                </button>
                <span>Page <strong>{page}</strong> of <strong>{pageCount}</strong></span>
                <button type="button" className="secondary-button" onClick={() => setPage((current) => Math.min(pageCount, current + 1))} disabled={page === pageCount}>
                  Next
                </button>
              </nav>
            )}
          </>
        )}

        {activeTab === "discovery" && (
          <RuntimeRecordList
            title="Discovery queue"
            description="Valid candidates that have not yet been promoted and analyzed. Raw payload is available only on demand for auditability."
            items={discoveryQueue}
            emptyMessage="No discovery queue was returned by the latest dashboard population."
          />
        )}

        {activeTab === "blockers" && (
          <RuntimeRecordList
            title="Runtime blockers"
            description="Failures and degraded stages returned by the central pipeline, grouped into readable records instead of one large JSON dump."
            items={blockerRecords}
            emptyMessage={populateResult ? "No runtime blockers were returned by the latest central pipeline run." : "Populate the dashboard to capture runtime blockers."}
          />
        )}

        {activeTab === "rejected" && (
          <RuntimeRecordList
            title="Rejected entities"
            description="Entities rejected by the quantitative company gate, with full decision payload retained for audit."
            items={rejectedEntities}
            emptyMessage="No rejected entities were returned by the latest dashboard population."
          />
        )}
      </section>
    </div>
  );
}
