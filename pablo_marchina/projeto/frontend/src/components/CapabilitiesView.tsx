import { useEffect, useState } from "react";
import type { ProductCapabilityRead } from "../api/types";
import { getProductCapabilities } from "../api/product";

function statusLabel(status: string): { cls: string; text: string } {
  switch (status) {
    case "available": return { cls: "cap-ok", text: "Available" };
    case "unavailable": return { cls: "cap-bad", text: "Unavailable" };
    case "not_configured": return { cls: "cap-warn", text: "Not Configured" };
    case "missing_dependency": return { cls: "cap-warn", text: "Missing Dependency" };
    case "degraded": return { cls: "cap-warn", text: "Degraded" };
    case "disabled": return { cls: "cap-off", text: "Disabled" };
    case "experimental": return { cls: "cap-exp", text: "Experimental" };
    default: return { cls: "cap-off", text: status };
  }
}

export function CapabilitiesView() {
  const [caps, setCaps] = useState<ProductCapabilityRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setCaps(await getProductCapabilities());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  if (loading) return <div className="panel"><div className="panel-body"><p className="loading-text">Loading capabilities...</p></div></div>;

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

  const grouped: Record<string, ProductCapabilityRead[]> = {};
  for (const cap of caps) {
    if (!grouped[cap.category]) grouped[cap.category] = [];
    grouped[cap.category].push(cap);
  }

  const categoryOrder = [
    "core", "database", "rag", "evidence", "claims", "playbooks",
    "dossier", "quality", "structured_outputs", "llm_judge",
    "export", "frontend", "developer_tools",
  ];

  return (
    <div className="capabilities-page">
      <div className="panel">
        <div className="panel-header">
          <h2>Product Capabilities</h2>
          <button type="button" className="secondary-button" onClick={load}>Refresh</button>
        </div>
      </div>

      {categoryOrder.map((cat) => {
        const items = grouped[cat];
        if (!items || items.length === 0) return null;
        return (
          <div key={cat} className="panel">
            <div className="panel-header">
              <h2 className="cap-category-title">{cat.replace(/_/g, " ")}</h2>
            </div>
            <div className="panel-body">
              <table className="cap-table">
                <thead>
                  <tr>
                    <th>Capability</th>
                    <th>Status</th>
                    <th>Env Vars</th>
                    <th>Extras</th>
                    <th>Instructions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((cap) => {
                    const st = statusLabel(cap.status);
                    return (
                      <tr key={cap.capability_id}>
                        <td>
                          <strong>{cap.name}</strong>
                          <span className="cell-desc">{cap.description}</span>
                        </td>
                        <td>
                          <span className={`badge ${st.cls}`}>{st.text}</span>
                          {cap.status_reason && (
                            <span className="cell-hint">{cap.status_reason}</span>
                          )}
                        </td>
                        <td>
                          {cap.required_env_vars.length > 0
                            ? cap.required_env_vars.map((v) => (
                                <code key={v} className="inline-code">{v}</code>
                              ))
                            : <span className="muted">—</span>}
                        </td>
                        <td>
                          {cap.required_extras.length > 0
                            ? cap.required_extras.map((e) => (
                                <code key={e} className="inline-code">{e}</code>
                              ))
                            : <span className="muted">—</span>}
                        </td>
                        <td>
                          {cap.setup_instructions ? (
                            <span className="cell-instruction">{cap.setup_instructions}</span>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </div>
  );
}
