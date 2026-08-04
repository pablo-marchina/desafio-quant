import type { AnalysisEvidenceBundle, ClaimRead, JsonValue } from "../api/types";

interface EvidenceFirstRunViewProps {
  bundle: AnalysisEvidenceBundle | null;
}

function percent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  return `${Math.round(value * 100)}%`;
}

function asText(value: JsonValue | undefined): string {
  if (value == null) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function badgeClass(value: string): string {
  if (["high", "ready", "supported", "strong", "completed", "pass"].includes(value.toLowerCase())) return "cap-ok";
  if (["medium", "degraded", "weak", "unknown", "warn"].includes(value.toLowerCase())) return "cap-warn";
  if (["low", "blocked", "failed", "unsupported", "error", "fail"].includes(value.toLowerCase())) return "cap-bad";
  return "cap-off";
}

function ClaimList({ title, claims }: { title: string; claims: ClaimRead[] }) {
  return (
    <div className="evidence-section">
      <div className="evidence-section-title">
        <h3>{title}</h3>
        <span className="badge cap-off">{claims.length}</span>
      </div>
      {claims.length === 0 ? (
        <p className="muted compact-text">No claims in this group.</p>
      ) : (
        <div className="evidence-list">
          {claims.map((claim) => (
            <article key={claim.id} className="evidence-item">
              <div className="evidence-item-head">
                <strong>{claim.claim_type}</strong>
                <span className={`badge ${badgeClass(claim.support_level)}`}>{claim.support_level}</span>
              </div>
              <p>{claim.claim_text}</p>
              <div className="evidence-item-meta">
                <span>Confidence: {claim.confidence}</span>
                <span>Refs: {claim.evidence_refs.length}</span>
                <span>Review: {claim.review_status}</span>
              </div>
            </article>
          ))}
        </div>
      )}
      {claims.length > 8 && <p className="muted compact-text">Showing 8 of {claims.length} claims.</p>}
    </div>
  );
}

export function EvidenceFirstRunView({ bundle }: EvidenceFirstRunViewProps) {
  if (!bundle) {
    return (
      <div className="panel">
        <div className="panel-header"><h2>Evidence Bundle</h2></div>
        <div className="panel-body">
          <div className="message warning-message">
            Evidence bundle is not available for this run yet. Existing run data remains visible below.
          </div>
        </div>
      </div>
    );
  }

  const claims = bundle.claims ?? {};
  const ragAvailable = bundle.rag_support.available === true;
  const supportingRefs = asText(bundle.rag_support.supporting_refs_count);
  const degraded = bundle.degraded_checks.length;
  const missingEvidence = bundle.missing_evidence;
  const alternatives = bundle.alternatives_lost;

  return (
    <div className="evidence-first-page">
      <div className="panel evidence-first-panel">
        <div className="panel-header">
          <h2>Evidence-First Bundle</h2>
          <span className={`badge ${badgeClass(bundle.readiness)}`}>{bundle.readiness}</span>
        </div>
        <div className="panel-body">
          <div className="evidence-metric-grid">
            <div className="evidence-metric">
              <span>Confidence</span>
              <strong>{bundle.confidence}</strong>
            </div>
            <div className="evidence-metric">
              <span>Coverage</span>
              <strong>{percent(bundle.evidence_coverage.evidence_coverage)}</strong>
            </div>
            <div className="evidence-metric">
              <span>Unsupported</span>
              <strong>{bundle.evidence_coverage.unsupported_claims}</strong>
            </div>
            <div className="evidence-metric">
              <span>Critical</span>
              <strong>{bundle.evidence_coverage.critical_supported_claims}/{bundle.evidence_coverage.critical_claims}</strong>
            </div>
            <div className="evidence-metric">
              <span>Recommendations</span>
              <strong>{bundle.recommendations.length}</strong>
            </div>
            <div className="evidence-metric">
              <span>Degraded</span>
              <strong>{degraded}</strong>
            </div>
          </div>

          {!ragAvailable && (
            <div className="message warning-message evidence-warning">
              RAG/Qdrant support is not fully available for this run. Recommendations must be treated as unproven until retrieval evidence is restored.
            </div>
          )}

          <div className="evidence-mini-grid">
            <div>
              <span className="muted">Supporting refs</span>
              <strong>{supportingRefs || "0"}</strong>
            </div>
            <div>
              <span className="muted">Pipeline</span>
              <strong>{asText(bundle.trust_freshness.pipeline_version) || "n/a"}</strong>
            </div>
            <div>
              <span className="muted">Corpus</span>
              <strong>{asText(bundle.trust_freshness.corpus_version) || "n/a"}</strong>
            </div>
            <div>
              <span className="muted">Dossier</span>
              <strong>{bundle.dossier ? `v${bundle.dossier.version}` : "not available"}</strong>
            </div>
          </div>
        </div>
      </div>

      <div className="evidence-columns-2">
        <ClaimList title="Supported Claims" claims={claims.supported ?? []} />
        <ClaimList title="Weak or Unsupported Claims" claims={[...(claims.weak ?? []), ...(claims.unsupported ?? [])]} />
      </div>

      <div className="evidence-columns-2">
        <ClaimList title="Critical Claims" claims={claims.critical ?? []} />
        <div className="panel">
          <div className="panel-header"><h2>Recommendations</h2></div>
          <div className="panel-body">
            {bundle.recommendations.length === 0 ? (
              <div className="message warning-message">No persisted activation recommendations are available for this run.</div>
            ) : (
              <div className="evidence-list">
                {bundle.recommendations.map((rec) => (
                  <article key={rec.id || rec.playbook_id} className="evidence-item">
                    <div className="evidence-item-head">
                      <strong>{rec.playbook_name}</strong>
                      <span className={`badge ${badgeClass(rec.confidence)}`}>{rec.confidence}</span>
                    </div>
                    <p>{rec.reasoning || "No reasoning was persisted."}</p>
                    <div className="evidence-item-meta">
                      <span>Motion: {rec.recommended_motion || "n/a"}</span>
                      <span>Priority: {rec.priority}</span>
                      <span>Refs: {rec.evidence_refs.length}</span>
                    </div>
                    {rec.next_step && <p className="compact-text"><strong>Next action:</strong> {rec.next_step}</p>}
                    {rec.risks.length > 0 && <p className="compact-text"><strong>Risks:</strong> {rec.risks.join("; ")}</p>}
                  </article>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="evidence-columns-2">
        <div className="panel">
          <div className="panel-header"><h2>Missing Evidence</h2></div>
          <div className="panel-body">
            {missingEvidence.length === 0 ? (
              <p className="muted">No missing evidence was reported by persisted checks.</p>
            ) : (
              <div className="evidence-list">
                {missingEvidence.map((item, index) => (
                  <article key={index} className="evidence-item">
                    <div className="evidence-item-head">
                      <strong>{asText(item.type) || "missing evidence"}</strong>
                      {item.support_level && <span className={`badge ${badgeClass(asText(item.support_level))}`}>{asText(item.support_level)}</span>}
                    </div>
                    <p>{asText(item.claim_text) || asText(item.code) || asText(item.score_type) || asText(item.gap_type)}</p>
                    <p className="compact-text">{asText(item.recommended_action) || asText(item.missing_evidence)}</p>
                  </article>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header"><h2>Alternatives Lost</h2></div>
          <div className="panel-body">
            {alternatives.length === 0 ? (
              <p className="muted">No non-promoted playbooks were reported.</p>
            ) : (
              <div className="evidence-list">
                {alternatives.map((item) => (
                  <article key={asText(item.playbook_id)} className="evidence-item">
                    <div className="evidence-item-head">
                      <strong>{asText(item.playbook_name)}</strong>
                      <span className="badge cap-off">{asText(item.playbook_id)}</span>
                    </div>
                    <p>{asText(item.reason_lost)}</p>
                    <p className="compact-text"><strong>Evidence needed:</strong> {asText(item.evidence_needed) || "n/a"}</p>
                  </article>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {bundle.contradictions.length > 0 && (
        <div className="panel">
          <div className="panel-header"><h2>Contradictions</h2></div>
          <div className="panel-body">
            <div className="evidence-list">
              {bundle.contradictions.map((item, index) => (
                <article key={index} className="evidence-item">
                  <strong>{asText(item.type)}</strong>
                  <p>{asText(item.claim_text) || asText(item.message)}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
