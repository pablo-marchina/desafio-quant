import { useEffect, useRef, useState, useMemo, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  PipelineStatus,
  type PipelineStepData,
} from "@/components/pipeline-status";
import { useRun } from "@/lib/hooks/use-runs";
import { submitRun } from "@/lib/api";
import type { PipelineStepRecord } from "@/lib/api";

const STEP_KEYS = [
  "search_planner",
  "scraper",
  "extractor",
  "validator",
  "classifier",
  "nvidia_rag",
  "recommendation",
  "briefing",
];

function mapStepStatus(
  status: PipelineStepRecord["status"],
): PipelineStepData["status"] {
  if (status === "completed") return "done";
  if (status === "failed") return "error";
  if (status === "pending") return "idle";
  if (status === "idle" || status === "running" || status === "error")
    return status;
  return "idle";
}

interface PipelineDialogProps {
  query: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onComplete?: () => void;
}

export function PipelineDialog({
  query,
  open,
  onOpenChange,
  onComplete,
}: PipelineDialogProps) {
  const [runId, setRunId] = useState<number | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [hasRun, setHasRun] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const runQuery = useRun(runId);

  const isRunning =
    runQuery.data?.status === "pending" ||
    runQuery.data?.status === "running" ||
    !hasRun;

  const hasResult = runQuery.data?.status === "completed";
  const hasError = runQuery.data?.status === "failed";

  useEffect(() => {
    if (!open || !query.trim()) return;

    setRunId(null);
    setStartedAt(Date.now());
    setElapsed(0);
    setHasRun(false);

    submitRun({ query })
      .then((res) => {
        setRunId(res.run_id);
        setHasRun(true);
      })
      .catch(() => {
        setHasRun(true);
      });

    return () => {
      setRunId(null);
    };
  }, [open, query]);

  useEffect(() => {
    if (runQuery.data?.status === "pending" || runQuery.data?.status === "running") {
      timerRef.current = setInterval(() => {
        setElapsed(Math.floor((Date.now() - (startedAt ?? Date.now())) / 1000));
      }, 1000);
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [runQuery.data?.status, startedAt]);

  useEffect(() => {
    if ((hasResult || hasError) && hasRun) {
      const timer = setTimeout(() => {
        onOpenChange(false);
        onComplete?.();
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [hasResult, hasError, hasRun, onOpenChange, onComplete]);

  const steps = useMemo<PipelineStepData[]>(() => {
    if (!runId || !hasRun) return [];

    const apiSteps = runQuery.data?.steps;
    if (!apiSteps || apiSteps.length === 0) {
      return STEP_KEYS.map((key) => ({
        key,
        status: (isRunning ? "idle" : hasResult ? "done" : "idle") as PipelineStepData["status"],
      }));
    }

    return STEP_KEYS.map((key) => {
      const api = apiSteps.find((s) => s.step_key === key);
      if (!api) return { key, status: "idle" as const };

      const status = mapStepStatus(api.status);
      const started = api.started_at ? new Date(api.started_at).getTime() : null;
      const completed = api.completed_at ? new Date(api.completed_at).getTime() : null;

      return {
        key,
        status,
        detail: api.detail ?? undefined,
        errorMessage: api.error_message ?? undefined,
        elapsedSeconds:
          status === "running" && started
            ? Math.floor((Date.now() - started) / 1000)
            : started && completed
              ? Math.floor((completed - started) / 1000)
              : undefined,
      };
    });
  }, [runQuery.data?.steps, runId, hasRun, isRunning, hasResult]);

  const displayElapsed = useMemo(() => {
    const created = runQuery.data?.created_at;
    if (!created) return elapsed;
    const startTs = Date.parse(created);
    if (Number.isNaN(startTs)) return elapsed;
    const completed = runQuery.data?.completed_at;
    const endTs = completed ? Date.parse(completed) : Date.now();
    return Math.floor((endTs - startTs) / 1000);
  }, [elapsed, runQuery.data?.completed_at, runQuery.data?.created_at]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            Pipeline Multiagente — {query}
          </DialogTitle>
        </DialogHeader>
        <PipelineStatus
          steps={steps}
          elapsedSeconds={displayElapsed}
          overallStatus={
            hasResult ? "completed" : hasError ? "error" : "pending"
          }
        />
      </DialogContent>
    </Dialog>
  );
}
