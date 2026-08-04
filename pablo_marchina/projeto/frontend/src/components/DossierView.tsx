import { useEffect, useState } from "react";
import type { ActivationDossierRead } from "../api/types";
import { getDossier, getDossierMarkdown, generateDossier } from "../api/product";

interface DossierViewProps {
  runId: string;
  onBack: () => void;
}

export function DossierView({ runId, onBack }: DossierViewProps) {
  const [dossier, setDossier] = useState<ActivationDossierRead | null>(null);
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showJson, setShowJson] = useState(false);
  const [copied, setCopied] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [d, m] = await Promise.all([
        getDossier(runId).catch(async () => {
          await generateDossier(runId);
          return getDossier(runId);
        }),
        getDossierMarkdown(runId).catch(() => null),
      ]);
      setDossier(d);
      setMarkdown(m?.markdown ?? d.dossier_markdown);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [runId]);

  async function handleCopy() {
    if (!markdown) return;
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard not available
    }
  }

  async function handleRegenerate() {
    setLoading(true);
    try {
      const result = await generateDossier(runId, true);
      setDossier(result.dossier);
      setMarkdown(result.dossier.dossier_markdown);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <div className="panel"><div className="panel-body"><p className="loading-text">Loading dossier...</p></div></div>;

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

  return (
    <div className="dossier-page">
      <div className="panel">
        <div className="panel-header">
          <div className="panel-header-left">
            <button type="button" className="back-button" onClick={onBack}>← Back</button>
            <h2>Activation Dossier</h2>
          </div>
          <div className="panel-header-actions">
            <button type="button" className="secondary-button" onClick={handleCopy}>
              {copied ? "Copied!" : "Copy Markdown"}
            </button>
            <button type="button" className="secondary-button" onClick={() => setShowJson(!showJson)}>
              {showJson ? "View Markdown" : "View Raw JSON"}
            </button>
            <button type="button" className="secondary-button" onClick={handleRegenerate}>
              Regenerate
            </button>
          </div>
        </div>
        <div className="panel-body">
          {dossier && (
            <>
              <div className="dossier-meta">
                <span className="muted">
                  v{dossier.version} | Coverage: {Math.round(dossier.evidence_coverage * 100)}% |
                  Motion: {dossier.recommended_motion} |
                  Unsupported claims: {dossier.unsupported_claim_count}
                </span>
              </div>

              {dossier.evidence_coverage < 0.5 && (
                <div className="message warning-message">
                  Low evidence coverage ({Math.round(dossier.evidence_coverage * 100)}%). Consider collecting more evidence before sharing this dossier externally.
                </div>
              )}

              {dossier.unsupported_claim_count > 3 && (
                <div className="message warning-message">
                  {dossier.unsupported_claim_count} unsupported claims found. Review and gather evidence for unsupported claims to strengthen the dossier.
                </div>
              )}

              {dossier.recommended_motion === "no_motion" && (
                <div className="message warning-message">
                  No recommended motion assigned. The dossier quality may be insufficient for activation decisions.
                </div>
              )}
            </>
          )}

          {showJson && dossier ? (
            <pre className="json-block">{JSON.stringify(dossier.dossier_json, null, 2)}</pre>
          ) : markdown ? (
            <pre className="markdown-block">{markdown}</pre>
          ) : (
            <p className="empty-state">No dossier content available.</p>
          )}
        </div>
      </div>
    </div>
  );
}
