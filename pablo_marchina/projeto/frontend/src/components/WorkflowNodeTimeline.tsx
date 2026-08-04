import type { ProductWorkflowNodeRunRead } from "../api/types";

interface WorkflowNodeTimelineProps {
  nodes: ProductWorkflowNodeRunRead[];
  currentNode: string;
}

function nodeStatusIcon(status: string): string {
  switch (status) {
    case "completed": return "✓";
    case "running": return "⟳";
    case "failed": return "✗";
    case "pending": return "○";
    default: return "○";
  }
}

function nodeStatusClass(status: string): string {
  switch (status) {
    case "completed": return "cap-ok";
    case "running": return "cap-exp";
    case "failed": return "cap-bad";
    default: return "cap-off";
  }
}

export function WorkflowNodeTimeline({ nodes, currentNode }: WorkflowNodeTimelineProps) {
  if (nodes.length === 0) {
    return <p className="empty-state">No nodes in this workflow run.</p>;
  }

  return (
    <div className="workflow-timeline">
      {nodes.map((node, i) => (
        <div key={node.id} className="workflow-node-row">
          <div className="workflow-node-marker">
            <div className={`workflow-node-icon ${nodeStatusClass(node.status)}`}>
              {nodeStatusIcon(node.status)}
            </div>
            {i < nodes.length - 1 && <div className="workflow-node-line" />}
          </div>
          <div className="workflow-node-card">
            <div className="workflow-node-header">
              <span className="workflow-node-name">{node.node_name}</span>
              {node.node_name === currentNode && (
                <span className="badge cap-exp">Current</span>
              )}
              <span className={`badge ${nodeStatusClass(node.status)}`}>
                {node.status}
              </span>
            </div>
            <div className="workflow-node-meta">
              {node.started_at && (
                <span className="muted">Started: {new Date(node.started_at).toLocaleString()}</span>
              )}
              {node.completed_at && (
                <span className="muted">Completed: {new Date(node.completed_at).toLocaleString()}</span>
              )}
              {node.retry_count > 0 && (
                <span className="text-warn">Retries: {node.retry_count}</span>
              )}
            </div>
            {node.error_message && (
              <div className="message error-message">{node.error_message}</div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}