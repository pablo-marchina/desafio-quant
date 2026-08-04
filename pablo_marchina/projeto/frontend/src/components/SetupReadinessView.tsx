import { useEffect, useState } from "react";
import type {
  ProductReadinessRead,
  ProductSetupChecklistRead,
} from "../api/types";
import {
  getProductReadiness,
  getProductSetupChecklist,
} from "../api/product";

interface SetupReadinessViewProps {
  onNavigate: (view: string) => void;
}

function useReadiness() {
  const [readiness, setReadiness] = useState<ProductReadinessRead | null>(null);
  const [checklist, setChecklist] = useState<ProductSetupChecklistRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [r, c] = await Promise.all([
        getProductReadiness(),
        getProductSetupChecklist(),
      ]);
      setReadiness(r);
      setChecklist(c);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  return { readiness, checklist, loading, error, refresh: load };
}

function EnvVarCopy({ key: envKey }: { key: string }) {
  return (
    <button
      type="button"
      className="badge-button"
      title="Copy env var name"
      onClick={() => navigator.clipboard.writeText(envKey)}
    >
      {envKey}
    </button>
  );
}

export function SetupReadinessView({ onNavigate }: SetupReadinessViewProps) {
  const { readiness, checklist, loading, error, refresh } = useReadiness();

  if (loading) {
    return <div className="panel"><div className="panel-body"><p className="loading-text">Checking product readiness...</p></div></div>;
  }

  if (error) {
    return (
      <div className="panel">
        <div className="panel-body">
          <div className="message error-message">{error}</div>
          <button type="button" className="secondary-button" onClick={refresh}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!readiness) return null;

  const progressPct = checklist
    ? Math.round((checklist.completed / Math.max(checklist.total, 1)) * 100)
    : 0;

  return (
    <div className="readiness-page">
      <div className="panel">
        <div className="panel-header">
          <h2>Product Status</h2>
          <button type="button" className="secondary-button" onClick={refresh}>
            Refresh
          </button>
        </div>
        <div className="panel-body">
          <div className={`status-badge-large ${readiness.ready ? "ok" : "bad"}`}>
            {readiness.ready ? "Ready" : "Not Ready"}
          </div>

          {readiness.user_messages.length > 0 && (
            <div className="messages-stack">
              {readiness.user_messages.map((msg, i) => (
                <div key={i} className="message info-message">{msg}</div>
              ))}
            </div>
          )}

          {checklist && (
            <div className="checklist-section">
              <h3>Setup Progress</h3>
              <div className="progress-bar-track">
                <div
                  className="progress-bar-fill"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
              <p className="progress-label">
                {checklist.completed} / {checklist.total} items done
              </p>
            </div>
          )}
        </div>
      </div>

      {!readiness.ready && readiness.blocking_missing_config.length > 0 && (
        <div className="panel panel-danger">
          <div className="panel-header"><h2>Blocking Configuration</h2></div>
          <div className="panel-body">
            {readiness.blocking_missing_config.map((item, i) => (
              <div key={i} className="config-item">
                <EnvVarCopy key={String(item.key || "")} />
                <span className="config-desc">{String(item.description || "")}</span>
              </div>
            ))}
            <p className="hint-text">
              Set these in your <code>.env</code> file or environment variables.
            </p>
          </div>
        </div>
      )}

      {readiness.optional_missing_config.length > 0 && (
        <div className="panel panel-warning">
          <div className="panel-header"><h2>Optional Configuration</h2></div>
          <div className="panel-body">
            {readiness.optional_missing_config.map((item, i) => {
              const extra = item.required_extra ? String(item.required_extra) : null;
              return (
                <div key={i} className="config-item">
                  <EnvVarCopy key={String(item.key || "")} />
                  <span className="config-desc">{String(item.description || "")}</span>
                  {extra && (
                    <code className="install-cmd">
                      pip install -e ".[{extra}]"
                    </code>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {readiness.unavailable_capabilities.length > 0 && (
        <div className="panel panel-warning">
          <div className="panel-header"><h2>Unavailable Capabilities</h2></div>
          <div className="panel-body compact-list">
            {readiness.unavailable_capabilities.map((cap, i) => (
              <div key={i} className="cap-row">
                <span className="cap-name">{String(cap.name || "")}</span>
                <span className="cap-reason">{String(cap.reason || cap.status_reason || "")}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {readiness.degraded_capabilities.length > 0 && (
        <div className="panel panel-warning">
          <div className="panel-header"><h2>Degraded Capabilities</h2></div>
          <div className="panel-body compact-list">
            {readiness.degraded_capabilities.map((cap, i) => (
              <div key={i} className="cap-row">
                <span className="cap-name">{String(cap.name || "")}</span>
                <span className="cap-reason">{String(cap.reason || "")}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {checklist && checklist.items.length > 0 && (
        <div className="panel">
          <div className="panel-header"><h2>Configuration Checklist</h2></div>
          <div className="panel-body">
            {checklist.items.map((item) => (
              <div key={item.key} className="checklist-row">
                <span className={`check-icon ${item.is_set ? "done" : "pending"}`}>
                  {item.is_set ? "✓" : "○"}
                </span>
                <span className="check-key">{item.key}</span>
                <span className="check-desc">{item.description}</span>
                {item.required && <span className="badge required-badge">required</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="panel">
        <div className="panel-header"><h2>Playwright E2E Tests</h2></div>
        <div className="panel-body">
          <p className="hint-text">
            E2E tests require Playwright browsers to be installed:
          </p>
          <div className="export-command-cmd">
            <code>npx playwright install chromium</code>
            <button
              type="button"
              className="badge-button"
              onClick={() => navigator.clipboard.writeText("npx playwright install chromium")}
            >
              Copy
            </button>
          </div>
          <p className="hint-text" style={{ marginTop: 8 }}>
            Run E2E tests: <code>npx playwright test</code>
            <br />
            The test runner starts both the backend (port 8000) and frontend (port 5173) automatically.
          </p>
          <p className="hint-text">
            See <code>tests/e2e/test_product_ui.spec.ts</code> for the full test suite.
          </p>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2>Product Quality</h2>
          <button type="button" className="secondary-button" onClick={() => onNavigate("quality")}>
            View Full Report
          </button>
        </div>
      </div>

      {readiness.ready && (
        <div className="cta-section">
          <button
            type="button"
            className="primary-button"
            onClick={() => onNavigate("startups")}
          >
            Go to Workspace
          </button>
        </div>
      )}
    </div>
  );
}
