import { useEffect, useMemo, useState } from "react";
import type {
  ActionBriefRead,
  ActivationDossierRead,
  AnalysisEvidenceBundle,
  AnalysisRunRead,
  ExportRead,
  JsonValue,
  OpportunityScoreCreateResponse,
  OpportunityScoreRead,
  ProductQualitySummaryRead,
  ProductWorkflowNodeRunRead,
  ProductWorkflowRunRead,
} from "../api/types";
import {
  computeOpportunityScore,
  createExport,
  generateDossier,
  getAnalysisEvidenceBundle,
  getAnalysisRun,
  getAnalysisRunBrief,
  getDossier,
  getDossierMarkdown,
  getExport,
  getOpportunityScore,
  getQualitySummary,
  getWorkflowRun,
} from "../api/product";
import { WorkflowNodeTimeline } from "./WorkflowNodeTimeline";

interface PipelineFinalResultViewProps {
  workflowId: string | null;
  onBackToWorkflow: () => void;
  onSelectStartup: (startupId: string) => void;
}

type StageKey =
  | "discovery"
  | "evidence"
  | "scoring"
  | "rag"
  | "techniques"
  | "recommendation"
  | "briefing"
  | "quality"
  | "export";

const NODE_STAGE: Record<string, StageKey> = {
  plan_search: "discovery",
  plan_missing_information: "discovery",
  collect_sources: "evidence",
  extract_profile: "evidence",
  validate_evidence: "evidence",
  score_startup_probabilistic: "scoring",
  diagnose_gaps: "scoring",
  retrieve_nvidia_context: "rag",
  enhance_contexts_with_techniques: "techniques",
  map_nvidia_technologies: "recommendation",
  rank_recommendations: "recommendation",
  rank_with_expected_utility: "recommendation",
  generate_brief: "briefing",
  run_quality_gates: "quality",
  generate_claims: "quality",
  match_activation_playbooks: "recommendation",
  generate_activation_dossier: "briefing",
  run_product_quality: "quality",
  summarize_readiness: "quality",
  needs_review: "quality",
  apply_feedback_weights: "quality",
  write_decision_ledger: "export",
};

function asRecord(value: unknown): Record<string, JsonValue> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, JsonValue>) : {};
}

function asArray(value: unknown): JsonValue[] {
  return Array.isArray(value) ? value : [];
}

function text(value: unknown, fallback = "—"): string {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function percent(value: unknown): string {
  const n = num(value);
  if (n === null) return "—";
  const normalized = n <= 1 ? n * 100 : n;
  return `${Math.round(normalized)}%`;
}

function score(value: unknown): string {
  const n = num(value);
  if (n === null) return "—";
  return n <= 1 ? n.toFixed(3) : n.toFixed(2);
}

function isTerminal(status: string): boolean {
  return ["completed", "failed", "degraded", "cancelled", "awaiting_review", "blocked"].includes(status);
}

function nodeDurationMs(node: ProductWorkflowNodeRunRead): number | null {
  if (!node.started_at || !node.completed_at) return null;
  const start = new Date(node.started_at).getTime();
  const end = new Date(node.completed_at).getTime();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return null;
  return end - start;
}

function StageCard({ title, stage, nodes }: { title: string; stage: StageKey; nodes: ProductWorkflowNodeRunRead[] }) {
  const stageNodes = nodes.filter((n) => NODE_STAGE[n.node_name] === stage);
  const failed = stageNodes.some((n) => n.status === "failed");
  const running = stageNodes.some((n) => n.status === "running");
  const completed = stageNodes.length > 0 && stageNodes.every((n) => ["completed", "skipped"].includes(n.status));
  const status = failed ? "failed" : running ? "running" : completed ? "completed" : "pending";
  const duration = stageNodes.reduce((acc, node) => acc + (nodeDurationMs(node) ?? 0), 0);

  return (
    <div className={`stage-card stage-${status}`}>
      <span>{title}</span>
      <strong>{status}</strong>
      <small>{stageNodes.length} nodes{duration ? ` · ${(duration / 1000).toFixed(1)}s` : ""}</small>
    </div>
  );
}

function RuntimeJson({ title, value }: { title: string; value: unknown }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="runtime-json">
      <button type="button" className="link-button" onClick={() => setOpen((v) => !v)}>
        {open ? "Hide" : "Show"} {title}
      </button>
      {open && <pre className="json-block compact-json-block">{JSON.stringify(value, null, 2)}</pre>}
    </div>
  );
}

function InfoGrid({ rows }: { rows: { label: string; value: unknown }[] }) {
  return (
    <div className="evidence-mini-grid">
      {rows.map((row) => (
        <div key={row.label}>
          <span className="muted">{row.label}</span>
          <strong>{text(row.value)}</strong>
        </div>
      ))}
    </div>
  );
}

function TableEmpty({ children }: { children: string }) {
  return <p className="empty-state">{children}</p>;
}

export function PipelineFinalResultView({ workflowId, onBackToWorkflow, onSelectStartup }: PipelineFinalResultViewProps) {
  const [workflow, setWorkflow] = useState<ProductWorkflowRunRead | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisRunRead | null>(null);
  const [bundle, setBundle] = useState<AnalysisEvidenceBundle | null>(null);
  const [brief, setBrief] = useState<ActionBriefRead | null>(null);
  const [quality, setQuality] = useState<ProductQualitySummaryRead | null>(null);
  const [dossier, setDossier] = useState<ActivationDossierRead | null>(null);
  const [dossierMarkdown, setDossierMarkdown] = useState<string | null>(null);
  const [opportunity, setOpportunity] = useState<OpportunityScoreRead | OpportunityScoreCreateResponse | null>(null);
  const [exportRead, setExportRead] = useState<ExportRead | null>(null);
  const [loading, setLoading] = useState(false);
  const [autoRefreshing, setAutoRefreshing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadWarnings, setLoadWarnings] = useState<string[]>([]);

  const analysisRunId = workflow?.analysis_run_id ?? analysis?.id ?? null;
  const workflowState = asRecord(workflow?.state ?? null);
  const nodeOutputs = asRecord(workflowState.node_outputs ?? null);
  const ragOutput = asRecord(nodeOutputs.retrieve_nvidia_context ?? nodeOutputs.rag_output ?? workflowState.rag_runtime_metrics ?? null);
  const ragMetrics = asRecord(ragOutput.rag_retrieval_metrics ?? ragOutput.rag_metrics ?? workflowState.rag_runtime_metrics ?? ragOutput);
  const techniquesOutput = asRecord(nodeOutputs.enhance_contexts_with_techniques ?? workflowState.technique_runtime_metrics ?? null);
  const recommendationOutput = asRecord(nodeOutputs.rank_recommendations ?? nodeOutputs.nvidia_recommendation_result ?? nodeOutputs.rank_with_expected_utility ?? null);
  const rankedRecommendations = asArray(workflowState.ranked_recommendations ?? recommendationOutput.ranked_recommendations ?? recommendationOutput.nvidia_recommendations ?? null);
  const nvidiaContexts = asArray(workflowState.nvidia_contexts ?? ragOutput.nvidia_contexts ?? null);
  const startupProfile = asRecord(workflowState.startup_profile ?? analysis?.output_snapshot?.startup_profile ?? null);
  const scores = asRecord(workflowState.scores ?? null);
  const gapOutput = asRecord(nodeOutputs.gap_output ?? null);
  const gapRows = asArray(gapOutput.gaps ?? analysis?.gaps ?? []);
  const collectionMetrics = asRecord(nodeOutputs.collection_metrics ?? null);

  async function loadWorkflow(id = workflowId) {
    if (!id) return;
    setLoading(true);
    setError(null);
    const warnings: string[] = [];
    try {
      const wf = await getWorkflowRun(id);
      setWorkflow(wf);
      if (wf.analysis_run_id) {
        const [ar, eb, br, q] = await Promise.all([
          getAnalysisRun(wf.analysis_run_id).catch((err) => { warnings.push(`Analysis run unavailable: ${String(err)}`); return null; }),
          getAnalysisEvidenceBundle(wf.analysis_run_id).catch((err) => { warnings.push(`Evidence bundle unavailable: ${String(err)}`); return null; }),
          getAnalysisRunBrief(wf.analysis_run_id).catch((err) => { warnings.push(`Brief unavailable: ${String(err)}`); return null; }),
          getQualitySummary(wf.analysis_run_id).catch((err) => { warnings.push(`Quality summary unavailable: ${String(err)}`); return null; }),
        ]);
        setAnalysis(ar);
        setBundle(eb);
        setBrief(br);
        setQuality(q);
        const [d, md, opp] = await Promise.all([
          getDossier(wf.analysis_run_id).catch((err) => { warnings.push(`Dossier unavailable: ${String(err)}`); return null; }),
          getDossierMarkdown(wf.analysis_run_id).catch((err) => { warnings.push(`Dossier markdown unavailable: ${String(err)}`); return null; }),
          getOpportunityScore(wf.analysis_run_id).catch((err) => { warnings.push(`Opportunity score unavailable: ${String(err)}`); return null; }),
        ]);
        setDossier(d);
        setDossierMarkdown(md?.markdown ?? d?.dossier_markdown ?? null);
        setOpportunity(opp);
      }
      setAutoRefreshing(!isTerminal(wf.status));
      setLoadWarnings(warnings);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadWorkflow(); }, [workflowId]);

  useEffect(() => {
    if (!workflowId || !autoRefreshing) return;
    const handle = window.setInterval(() => { loadWorkflow(workflowId); }, 3000);
    return () => window.clearInterval(handle);
  }, [workflowId, autoRefreshing]);

  async function generateFinalArtifacts() {
    if (!analysisRunId) return;
    setGenerating(true);
    setError(null);
    try {
      await generateDossier(analysisRunId, true).catch(() => null);
      const opp = await computeOpportunityScore(analysisRunId).catch(() => null);
      if (opp) setOpportunity(opp);
      const ex = await createExport(analysisRunId, "final_delivery_markdown");
      const fullExport = await getExport(ex.id).catch(() => ex);
      setExportRead(fullExport);
      const [d, md, br, q, eb, ar] = await Promise.all([
        getDossier(analysisRunId).catch(() => null),
        getDossierMarkdown(analysisRunId).catch(() => null),
        getAnalysisRunBrief(analysisRunId).catch(() => null),
        getQualitySummary(analysisRunId).catch(() => null),
        getAnalysisEvidenceBundle(analysisRunId).catch(() => null),
        getAnalysisRun(analysisRunId).catch(() => null),
      ]);
      setDossier(d);
      setDossierMarkdown(md?.markdown ?? d?.dossier_markdown ?? null);
      setBrief(br);
      setQuality(q);
      setBundle(eb);
      setAnalysis(ar);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setGenerating(false);
    }
  }

  async function copyFinalMarkdown() {
    const content = typeof exportRead?.content === "string" ? exportRead.content : dossierMarkdown || brief?.brief_markdown || "";
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard may be unavailable in non-secure contexts.
    }
  }

  const allClaims = useMemo(() => {
    if (!bundle) return [];
    return Object.entries(bundle.claims).flatMap(([group, claims]) => claims.map((claim) => ({ group, claim })));
  }, [bundle]);

  const topRecommendations = useMemo(() => {
    const fromRun = analysis?.nvidia_mappings ?? [];
    if (rankedRecommendations.length > 0) return rankedRecommendations;
    return fromRun as unknown as JsonValue[];
  }, [analysis?.nvidia_mappings, rankedRecommendations]);

  const primaryRecommendation = asRecord(topRecommendations[0] ?? null);
  const opportunityScore = "opportunity_score" in (opportunity ?? {}) ? (opportunity as OpportunityScoreRead).opportunity_score : (opportunity as OpportunityScoreCreateResponse | null)?.opportunity_score;
  const opportunityTier = "score_tier" in (opportunity ?? {}) ? text((opportunity as OpportunityScoreRead | OpportunityScoreCreateResponse).score_tier) : "—";
  const recommendedAction = text(primaryRecommendation.recommendation_action ?? primaryRecommendation.next_best_action ?? (opportunity as OpportunityScoreRead | null)?.recommended_action ?? dossier?.recommended_motion, "validate_manually");
  const blockers = [
    ...(workflow?.error_message ? [workflow.error_message] : []),
    ...(workflow?.degraded_reason ? [workflow.degraded_reason] : []),
    ...(quality?.degraded_reason ? [quality.degraded_reason] : []),
    ...loadWarnings,
    ...(bundle?.degraded_checks ?? []).map((check) => `${check.code}: ${check.user_message}`),
    ...asArray(recommendationOutput.blockers).map((item) => text(item)),
  ].filter(Boolean);

  const totalNodes = workflow?.nodes.length ?? 0;
  const completedNodes = workflow?.nodes.filter((n) => n.status === "completed").length ?? 0;
  const failedNodes = workflow?.nodes.filter((n) => n.status === "failed").length ?? 0;
  const progress = totalNodes ? Math.round((completedNodes / totalNodes) * 100) : 0;

  if (!workflowId) {
    return (
      <div className="panel">
        <div className="panel-body">
          <p className="empty-state">No workflow selected. Start the main pipeline from a startup or select a workflow run.</p>
          <button type="button" className="secondary-button" onClick={onBackToWorkflow}>Go to Workflow</button>
        </div>
      </div>
    );
  }

  return (
    <div className="final-result-page decision-cockpit-page">
      <div className="final-hero panel">
        <div className="panel-body final-hero-body">
          <div>
            <p className="eyebrow">NVIDIA Startup Decision Cockpit</p>
            <h2>Final Pipeline Result</h2>
            <p className="muted">
              Decision-first view of the single runtime pipeline: approach decision, startup profile, NVIDIA opportunity,
              recommendations, evidence matrix, RAG support, quality gates and audit trace.
            </p>
          </div>
          <div className="final-hero-actions">
            <button type="button" className="secondary-button" onClick={() => loadWorkflow()} disabled={loading}>Refresh</button>
            <button type="button" className="primary-button compact-primary-button" onClick={generateFinalArtifacts} disabled={!analysisRunId || generating}>
              {generating ? "Generating..." : "Generate Final Deliverables"}
            </button>
            <button type="button" className="secondary-button" onClick={copyFinalMarkdown} disabled={!exportRead?.content && !dossierMarkdown && !brief?.brief_markdown}>
              {copied ? "Copied" : "Copy Final Output"}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="message error-message">{error}</div>}
      {loading && <p className="loading-text">Loading final result...</p>}

      {workflow && (
        <>
          {blockers.length > 0 && (
            <div className="message warning-message">
              <strong>Runtime blockers / warnings</strong>
              <ul>{blockers.map((item, index) => <li key={index}>{item}</li>)}</ul>
            </div>
          )}

          <div className="final-summary-grid decision-summary-grid">
            <div className="summary-tile decision-tile">
              <span>Recommended NVIDIA action</span>
              <strong>{recommendedAction}</strong>
              <small>{text(primaryRecommendation.next_best_action ?? primaryRecommendation.reason ?? "Open recommendation details below")}</small>
            </div>
            <div className="summary-tile">
              <span>Opportunity score</span>
              <strong>{score(opportunityScore)}</strong>
              <small>Tier {opportunityTier}</small>
            </div>
            <div className="summary-tile">
              <span>Top NVIDIA technology</span>
              <strong>{text(primaryRecommendation.nvidia_technology ?? primaryRecommendation.technology ?? primaryRecommendation.product)}</strong>
              <small>Expected utility {score(primaryRecommendation.expected_utility ?? primaryRecommendation.recommendation_priority_score)}</small>
            </div>
            <div className="summary-tile">
              <span>Evidence coverage</span>
              <strong>{percent(bundle?.evidence_coverage.evidence_coverage ?? analysis?.claim_summary?.evidence_coverage)}</strong>
              <small>{bundle?.evidence_coverage.unsupported_claims ?? analysis?.claim_summary?.unsupported_claims ?? "—"} unsupported claims</small>
            </div>
            <div className="summary-tile">
              <span>Workflow status</span>
              <strong className={`status-text status-${workflow.status}`}>{workflow.status}</strong>
              <small>{workflow.current_node || "—"}</small>
            </div>
            <div className="summary-tile">
              <span>Pipeline progress</span>
              <strong>{progress}%</strong>
              <small>{completedNodes}/{totalNodes} nodes completed · {failedNodes} failed</small>
            </div>
          </div>

          <div className="panel priority-panel">
            <div className="panel-header"><h2>1. Startup intelligence profile</h2></div>
            <div className="panel-body">
              <InfoGrid rows={[
                { label: "Startup", value: startupProfile.name ?? startupProfile.startup_name ?? analysis?.startup_id ?? workflow.startup_id },
                { label: "Website", value: startupProfile.website ?? startupProfile.website_url },
                { label: "Sector", value: startupProfile.sector ?? startupProfile.industry },
                { label: "Product", value: startupProfile.product_summary ?? startupProfile.description },
                { label: "AI-native classification", value: asRecord(workflowState.classification_result).classification ?? asRecord(workflowState.classification_result).label },
                { label: "AI-native score", value: scores.probabilistic_score ?? scores.score },
                { label: "NVIDIA/Inception fit", value: scores.inception_fit ?? scores.nvidia_fit_score },
                { label: "Sources collected", value: collectionMetrics.raw_evidence_count },
                { label: "Distinct sources", value: collectionMetrics.distinct_source_count },
                { label: "Official sources", value: collectionMetrics.official_source_count },
              ]} />
              <RuntimeJson title="complete startup profile state" value={startupProfile} />
            </div>
          </div>

          <div className="panel priority-panel">
            <div className="panel-header"><h2>2. NVIDIA recommendation ranking — all recommendations</h2></div>
            <div className="panel-body">
              {topRecommendations.length === 0 ? (
                <TableEmpty>No ranked recommendations have been persisted yet.</TableEmpty>
              ) : (
                <div className="recommendation-grid full-recommendation-grid">
                  {topRecommendations.map((item, index) => {
                    const rec = asRecord(item);
                    const whyNot = asArray(rec.why_not ?? rec.blockers);
                    return (
                      <article key={index} className="recommendation-card">
                        <div className="recommendation-head">
                          <strong>{index + 1}. {text(rec.nvidia_technology ?? rec.technology_name ?? rec.product ?? rec.playbook_name, `Recommendation ${index + 1}`)}</strong>
                          <span className="badge cap-ok">{score(rec.expected_utility ?? rec.recommendation_priority_score ?? rec.mapping_score)}</span>
                        </div>
                        <InfoGrid rows={[
                          { label: "Action", value: rec.recommendation_action ?? rec.next_best_action },
                          { label: "Gap", value: rec.gap_type ?? rec.addresses_gap },
                          { label: "Mapping score", value: rec.mapping_score },
                          { label: "Confidence", value: rec.confidence ?? rec.mapping_confidence },
                          { label: "Uncertainty", value: rec.uncertainty },
                          { label: "Business impact", value: rec.business_impact },
                          { label: "Complexity", value: rec.implementation_complexity },
                          { label: "Evidence support", value: rec.evidence_support_score },
                          { label: "RAG support", value: rec.rag_support_score },
                          { label: "Production allowed", value: rec.production_allowed },
                        ]} />
                        <p>{text(rec.reason ?? rec.reasoning ?? rec.recommendation_action ?? rec.next_best_action, "No reasoning persisted.")}</p>
                        <p><strong>Next best action:</strong> {text(rec.next_best_action)}</p>
                        {whyNot.length > 0 && (
                          <div className="blocker-list"><strong>Why not / blockers:</strong><ul>{whyNot.map((b, i) => <li key={i}>{text(b)}</li>)}</ul></div>
                        )}
                        <RuntimeJson title="complete recommendation object" value={rec} />
                      </article>
                    );
                  })}
                </div>
              )}
              <RuntimeJson title="recommendation runtime output" value={recommendationOutput} />
            </div>
          </div>

          <div className="panel priority-panel">
            <div className="panel-header"><h2>3. Evidence matrix — all collected/generated claims</h2></div>
            <div className="panel-body table-scroll">
              {bundle ? (
                <>
                  <div className="claim-summary-grid">
                    <div className="claim-stat"><span>Total claims</span><strong>{bundle.evidence_coverage.total_claims}</strong></div>
                    <div className="claim-stat"><span>Supported</span><strong>{bundle.evidence_coverage.supported_claims}</strong></div>
                    <div className="claim-stat"><span>Critical supported</span><strong>{bundle.evidence_coverage.critical_supported_claims}/{bundle.evidence_coverage.critical_claims}</strong></div>
                    <div className="claim-stat"><span>Coverage</span><strong>{percent(bundle.evidence_coverage.evidence_coverage)}</strong></div>
                  </div>
                  <table className="data-table evidence-matrix-table">
                    <thead><tr><th>Group</th><th>Claim</th><th>Type</th><th>Support</th><th>Confidence</th><th>Used in</th><th>Evidence refs</th><th>Review</th></tr></thead>
                    <tbody>
                      {allClaims.map(({ group, claim }) => (
                        <tr key={claim.id}>
                          <td>{group}</td>
                          <td>{claim.claim_text}</td>
                          <td>{claim.claim_type}</td>
                          <td>{claim.support_level}</td>
                          <td>{claim.confidence}</td>
                          <td>{[
                            claim.used_in_score ? "score" : "",
                            claim.used_in_gap ? "gap" : "",
                            claim.used_in_mapping ? "mapping" : "",
                            claim.used_in_brief ? "brief" : "",
                          ].filter(Boolean).join(", ") || "—"}</td>
                          <td>{claim.evidence_refs.length}</td>
                          <td>{claim.review_status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {bundle.missing_evidence.length > 0 && <RuntimeJson title="all missing evidence" value={bundle.missing_evidence} />}
                  {bundle.contradictions.length > 0 && <RuntimeJson title="all contradictions" value={bundle.contradictions} />}
                </>
              ) : (
                <TableEmpty>Evidence bundle is not available yet.</TableEmpty>
              )}
            </div>
          </div>

          <div className="panel priority-panel">
            <div className="panel-header"><h2>4. Technical gaps and NVIDIA context</h2></div>
            <div className="panel-body">
              <h3>Gap diagnosis</h3>
              {gapRows.length > 0 ? (
                <div className="table-scroll"><table className="data-table"><thead><tr><th>Gap</th><th>Severity</th><th>Confidence</th><th>Status</th><th>Evidence</th></tr></thead><tbody>{gapRows.map((gap, index) => {
                  const g = asRecord(gap);
                  return <tr key={index}><td>{text(g.gap_type ?? g.type ?? g.id)}</td><td>{score(g.severity_score ?? g.severity)}</td><td>{score(g.confidence_score ?? g.confidence)}</td><td>{text(g.production_allowed ?? g.status)}</td><td>{text(g.supporting_evidence_count ?? asArray(g.supporting_evidence_ids).length)}</td></tr>;
                })}</tbody></table></div>
              ) : <TableEmpty>No gap rows available yet.</TableEmpty>}
              <h3>NVIDIA RAG contexts — all contexts</h3>
              {nvidiaContexts.length > 0 ? (
                <div className="table-scroll"><table className="data-table rag-context-table"><thead><tr><th>Technology</th><th>Source</th><th>Score</th><th>Gap</th><th>Snippet</th></tr></thead><tbody>{nvidiaContexts.map((ctx, index) => {
                  const r = asRecord(ctx);
                  return <tr key={index}><td>{text(r.product ?? r.nvidia_technology ?? r.title)}</td><td>{text(r.source_id ?? r.url)}</td><td>{score(r.relevance_score ?? r.rerank_score ?? r.retrieval_score)}</td><td>{text(r.gap_type ?? r.gap_id ?? r.gap_types)}</td><td>{text(r.content ?? r.snippet, "No snippet persisted.")}</td></tr>;
                })}</tbody></table></div>
              ) : <TableEmpty>No NVIDIA contexts persisted yet.</TableEmpty>}
              <RuntimeJson title="RAG runtime metrics" value={ragOutput} />
              <RuntimeJson title="advanced techniques output" value={techniquesOutput} />
            </div>
          </div>

          <div className="stage-grid">
            <StageCard title="Discovery" stage="discovery" nodes={workflow.nodes} />
            <StageCard title="Evidence" stage="evidence" nodes={workflow.nodes} />
            <StageCard title="Scoring & gaps" stage="scoring" nodes={workflow.nodes} />
            <StageCard title="RAG" stage="rag" nodes={workflow.nodes} />
            <StageCard title="Techniques" stage="techniques" nodes={workflow.nodes} />
            <StageCard title="Recommendations" stage="recommendation" nodes={workflow.nodes} />
            <StageCard title="Briefing" stage="briefing" nodes={workflow.nodes} />
            <StageCard title="Quality/export" stage="quality" nodes={workflow.nodes} />
          </div>

          <div className="panel">
            <div className="panel-header"><h2>5. Quality gates and runtime trace</h2></div>
            <div className="panel-body">
              <InfoGrid rows={[
                { label: "Overall quality", value: quality?.overall_status },
                { label: "Passed metrics", value: quality ? `${quality.passed_metrics}/${quality.total_metrics}` : "—" },
                { label: "Export readiness", value: quality?.export_readiness_score },
                { label: "Review readiness", value: quality?.review_readiness_score },
                { label: "Pipeline quality gate", value: asRecord(workflowState.quality_gates_result).status },
                { label: "RAG retrieval mode", value: ragMetrics.retrieval_mode ?? ragOutput.retrieval_mode ?? workflowState.rag_retrieval_mode },
                { label: "GraphRAG", value: ragMetrics.graphrag_active ?? ragOutput.graphrag_enabled ?? workflowState.graphrag_enabled },
                { label: "Triton rerank", value: ragMetrics.triton_reranker_active ?? ragMetrics.triton_reranker_required ?? ragOutput.triton_reranker_enabled ?? workflowState.triton_reranker_enabled },
              ]} />
              <div className="progress-bar"><span style={{ width: `${progress}%` }} /></div>
              <WorkflowNodeTimeline nodes={workflow.nodes} currentNode={workflow.current_node} />
              <RuntimeJson title="workflow state" value={workflow.state} />
            </div>
          </div>

          <div className="final-two-column">
            <div className="panel">
              <div className="panel-header"><h2>Executive Brief</h2></div>
              <div className="panel-body">
                {brief ? <pre className="markdown-block final-markdown-block">{brief.brief_markdown}</pre> : <p className="empty-state">Brief not available yet.</p>}
              </div>
            </div>
            <div className="panel">
              <div className="panel-header"><h2>Activation Dossier</h2></div>
              <div className="panel-body">
                {dossier ? (
                  <>
                    <div className="dossier-meta"><span className="muted">v{dossier.version} · Coverage {percent(dossier.evidence_coverage)} · Motion {dossier.recommended_motion}</span></div>
                    <pre className="markdown-block final-markdown-block">{dossierMarkdown || dossier.dossier_markdown}</pre>
                  </>
                ) : <p className="empty-state">Dossier not available yet. Generate final deliverables when the run completes.</p>}
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-header"><h2>Final Export</h2></div>
            <div className="panel-body">
              {exportRead ? (
                <>
                  <InfoGrid rows={[
                    { label: "Export ID", value: exportRead.id },
                    { label: "Type", value: exportRead.export_type },
                    { label: "Status", value: exportRead.status },
                    { label: "Hash", value: exportRead.content_hash || "—" },
                  ]} />
                  {typeof exportRead.content === "string" ? (
                    <pre className="markdown-block final-export-block">{exportRead.content}</pre>
                  ) : exportRead.content ? (
                    <pre className="json-block final-export-block">{JSON.stringify(exportRead.content, null, 2)}</pre>
                  ) : (
                    <p className="empty-state">Export exists but no content was returned by the API.</p>
                  )}
                </>
              ) : <p className="empty-state">No final export generated yet.</p>}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
