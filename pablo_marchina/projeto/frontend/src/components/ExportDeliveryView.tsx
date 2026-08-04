import { useMemo, useState } from "react";
import {
  computeOpportunityScore,
  createExport,
  generateDossier,
  getAnalysisRunBrief,
  getDossierMarkdown,
  getExport,
  getOpportunityScore,
  getQualityReport,
} from "../api/product";
import type { ExportRead } from "../api/types";

type StepStatus = "pending" | "running" | "done" | "failed";

interface DeliveryStep {
  id: string;
  label: string;
  status: StepStatus;
  detail?: string;
}

function asText(content: unknown): string {
  if (content == null) return "";
  if (typeof content === "string") return content;
  return JSON.stringify(content, null, 2);
}

export function ExportDeliveryView() {
  const [analysisRunId, setAnalysisRunId] = useState("");
  const [exportType, setExportType] = useState<"markdown" | "json">("markdown");
  const [exportId, setExportId] = useState("");
  const [exportRecord, setExportRecord] = useState<ExportRead | null>(null);
  const [content, setContent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [steps, setSteps] = useState<DeliveryStep[]>([
    { id: "brief", label: "Load quantitative action brief", status: "pending" },
    { id: "dossier", label: "Generate or refresh activation dossier", status: "pending" },
    { id: "opportunity", label: "Compute opportunity score", status: "pending" },
    { id: "quality", label: "Validate export readiness signals", status: "pending" },
    { id: "export", label: "Create final export artifact", status: "pending" },
    { id: "content", label: "Load export content for delivery", status: "pending" },
  ]);

  const completedCount = useMemo(() => steps.filter((s) => s.status === "done").length, [steps]);
  const allDone = completedCount === steps.length;

  function updateStep(id: string, status: StepStatus, detail?: string) {
    setSteps((prev) => prev.map((s) => (s.id === id ? { ...s, status, detail } : s)));
  }

  function reset() {
    setError(null);
    setExportRecord(null);
    setContent("");
    setCopied(false);
    setSteps((prev) => prev.map((s) => ({ ...s, status: "pending", detail: undefined })));
  }

  async function runExportFlow() {
    const runId = analysisRunId.trim();
    if (!runId) {
      setError("Informe um analysis_run_id antes de gerar o export.");
      return;
    }
    reset();
    try {
      updateStep("brief", "running");
      const brief = await getAnalysisRunBrief(runId);
      updateStep("brief", "done", `Brief version ${brief.version}`);

      updateStep("dossier", "running");
      await generateDossier(runId, true);
      const dossierMarkdown = await getDossierMarkdown(runId);
      updateStep("dossier", "done", `Dossier ${dossierMarkdown.dossier_id}, version ${dossierMarkdown.version}`);

      updateStep("opportunity", "running");
      await computeOpportunityScore(runId);
      const opportunity = await getOpportunityScore(runId);
      updateStep("opportunity", "done", `Score ${opportunity.opportunity_score.toFixed(3)} (${opportunity.score_tier})`);

      updateStep("quality", "running");
      const qualityReport = await getQualityReport();
      const exportThreshold = Number(
        qualityReport.thresholds?.export_readiness_score?.threshold ??
          qualityReport.thresholds?.recommendation_actionability_score?.threshold ??
          1,
      );
      const exportReady = opportunity.opportunity_score >= exportThreshold;
      updateStep(
        "quality",
        exportReady ? "done" : "failed",
        exportReady
          ? `Opportunity score meets backend-governed export-readiness threshold (${exportThreshold.toFixed(3)}).`
          : `Opportunity score below backend-governed export-readiness threshold: ${opportunity.opportunity_score.toFixed(3)} < ${exportThreshold.toFixed(3)}`,
      );
      if (!exportReady) {
        throw new Error("Export bloqueado: readiness quantitativo abaixo do mínimo governado pelo backend.");
      }

      updateStep("export", "running");
      const created = await createExport(runId, exportType);
      setExportRecord(created);
      setExportId(created.id);
      updateStep("export", "done", `Export ${created.id} (${created.export_type})`);

      updateStep("content", "running");
      const loaded = await getExport(created.id);
      setExportRecord(loaded);
      const loadedContent = asText(loaded.content);
      setContent(loadedContent);
      updateStep("content", loadedContent ? "done" : "failed", loadedContent ? "Content loaded." : "Export content unavailable from API.");
      if (!loadedContent) throw new Error("Export criado, mas o conteúdo não foi retornado pela API.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  async function loadExistingExport() {
    if (!exportId.trim()) {
      setError("Informe um export_id para carregar.");
      return;
    }
    setError(null);
    try {
      const loaded = await getExport(exportId.trim());
      setExportRecord(loaded);
      setAnalysisRunId(loaded.analysis_run_id);
      setContent(asText(loaded.content));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  async function copyContent() {
    if (!content) return;
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="export-delivery-page">
      <div className="panel">
        <div className="panel-header">
          <h2>Final Export Delivery</h2>
          <div className="panel-header-actions">
            <button type="button" className="secondary-button" onClick={reset}>Reset</button>
            <button type="button" className="primary-button" onClick={runExportFlow}>Generate Final Export</button>
          </div>
        </div>
        <div className="panel-body">
          {error && <div className="message error-message">{error}</div>}
          {allDone && <div className="message info-message">Export pronto para entrega.</div>}
          <div className="form-grid">
            <label>
              <span>Analysis Run ID</span>
              <input value={analysisRunId} onChange={(e) => setAnalysisRunId(e.target.value)} placeholder="analysis_run_id" />
            </label>
            <label>
              <span>Export Type</span>
              <select value={exportType} onChange={(e) => setExportType(e.target.value as "markdown" | "json")}>
                <option value="markdown">Markdown</option>
                <option value="json">JSON</option>
              </select>
            </label>
            <label>
              <span>Existing Export ID</span>
              <input value={exportId} onChange={(e) => setExportId(e.target.value)} placeholder="export_id" />
            </label>
            <div className="form-actions-inline">
              <button type="button" className="secondary-button" onClick={loadExistingExport}>Load Existing Export</button>
            </div>
          </div>

          <div className="progress-label">{completedCount} / {steps.length} automated delivery checks completed</div>
          <div className="checklist-section">
            {steps.map((step) => (
              <div key={step.id} className={`checklist-row status-${step.status}`}>
                <div>
                  <strong>{step.label}</strong>
                  {step.detail && <span>{step.detail}</span>}
                </div>
                <span className="status-pill">{step.status}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {exportRecord && (
        <div className="panel">
          <div className="panel-header"><h2>Export Metadata</h2></div>
          <div className="panel-body">
            <div className="metadata-grid">
              <div><strong>ID</strong><span>{exportRecord.id}</span></div>
              <div><strong>Status</strong><span>{exportRecord.status}</span></div>
              <div><strong>Type</strong><span>{exportRecord.export_type}</span></div>
              <div><strong>Storage Path</strong><span>{exportRecord.storage_path}</span></div>
              <div><strong>SHA-256</strong><span>{exportRecord.content_hash}</span></div>
            </div>
          </div>
        </div>
      )}

      <div className="panel">
        <div className="panel-header">
          <h2>Deliverable Content</h2>
          <button type="button" className="secondary-button" disabled={!content} onClick={copyContent}>{copied ? "Copied" : "Copy Content"}</button>
        </div>
        <div className="panel-body">
          {content ? <pre className="export-preview">{content}</pre> : <p className="hint-text">Generate or load an export to preview its content here.</p>}
        </div>
      </div>
    </div>
  );
}
