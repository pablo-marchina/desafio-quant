import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Search,
  Globe,
  FileText,
  Tags,
  ShieldCheck,
  BookOpen,
  Lightbulb,
  FileSpreadsheet,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
} from "lucide-react";

export type StepStatus = "idle" | "running" | "done" | "error";

interface Step {
  key: string;
  name: string;
  icon: typeof Search;
}

const PIPELINE_STEPS: Step[] = [
  { key: "search_planner", name: "Search Planner", icon: Search },
  { key: "scraper", name: "Scraper", icon: Globe },
  { key: "extractor", name: "Extractor", icon: FileText },
  { key: "validator", name: "Validator", icon: ShieldCheck },
  { key: "classifier", name: "Classifier", icon: Tags },
  { key: "nvidia_rag", name: "RAG Agent", icon: BookOpen },
  { key: "recommendation", name: "Recommendation", icon: Lightbulb },
  { key: "briefing", name: "Briefing", icon: FileSpreadsheet },
];

export interface PipelineStepData {
  key: string;
  status: StepStatus;
  elapsedSeconds?: number;
  errorMessage?: string;
  detail?: string;
}

interface PipelineStatusProps {
  steps: PipelineStepData[];
  elapsedSeconds: number;
  overallStatus: "pending" | "completed" | "error";
}

function StepIcon({ status, icon: Icon }: { status: StepStatus; icon: typeof Search }) {
  if (status === "running") return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
  if (status === "done") return <CheckCircle2 className="h-4 w-4 text-green-500" />;
  if (status === "error") return <XCircle className="h-4 w-4 text-destructive" />;
  return <Icon className="h-4 w-4 text-muted-foreground" />;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function PipelineStatus({ steps, elapsedSeconds, overallStatus }: PipelineStatusProps) {
  const doneCount = steps.filter((s) => s.status === "done").length;
  const total = steps.length;
  const progress = overallStatus === "pending" ? Math.round((doneCount / total) * 100) : 100;

  return (
    <div className="space-y-4">
      {/* Header with timer */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {overallStatus === "pending" && (
            <Badge className="gap-1.5 bg-primary text-primary-foreground animate-pulse">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> IA processando...
            </Badge>
          )}
          {overallStatus === "completed" && (
            <Badge className="gap-1.5 bg-green-600 text-white">
              <CheckCircle2 className="h-3.5 w-3.5" /> Pipeline concluído
            </Badge>
          )}
          {overallStatus === "error" && (
            <Badge variant="destructive" className="gap-1.5">
              <XCircle className="h-3.5 w-3.5" /> Pipeline falhou
            </Badge>
          )}
        </div>
        <span className="flex items-center gap-1 text-xs text-muted-foreground tabular-nums">
          <Clock className="h-3.5 w-3.5" /> {formatTime(elapsedSeconds)}
        </span>
      </div>

      {/* Progress bar */}
      <Progress value={progress} className="h-2" />

      {/* Pipeline steps */}
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map((step) => {
          const def = PIPELINE_STEPS.find((s) => s.key === step.key);
          if (!def) return null;
          const Icon = def.icon;

          return (
            <Card
              key={step.key}
              className={`p-3 transition-all ${
                step.status === "running"
                  ? "border-primary/50 ring-1 ring-primary/20"
                  : step.status === "error"
                    ? "border-destructive/50"
                    : ""
              }`}
            >
              <div className="flex items-center gap-2.5">
                <div
                  className={`grid h-8 w-8 shrink-0 place-items-center rounded-md ${
                    step.status === "running"
                      ? "bg-primary/10"
                      : step.status === "done"
                        ? "bg-green-500/10"
                        : step.status === "error"
                          ? "bg-destructive/10"
                          : "bg-muted"
                  }`}
                >
                  <StepIcon status={step.status} icon={Icon} />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">{def.name}</p>
                  {step.status === "running" && step.elapsedSeconds !== undefined && (
                    <p className="text-[11px] tabular-nums text-muted-foreground">
                      {formatTime(step.elapsedSeconds)}
                    </p>
                  )}
                  {step.status === "running" && !step.elapsedSeconds && step.detail && (
                    <p className="truncate text-[11px] text-muted-foreground animate-pulse">
                      {step.detail}
                    </p>
                  )}
                  {step.status === "running" && step.elapsedSeconds !== undefined && step.detail && (
                    <p className="truncate text-[11px] text-muted-foreground">
                      {step.detail}
                    </p>
                  )}
                  {step.status === "error" && step.errorMessage && (
                    <p className="truncate text-[11px] text-destructive">{step.errorMessage}</p>
                  )}
                  {step.status === "error" && !step.errorMessage && step.detail && (
                    <p className="truncate text-[11px] text-destructive">{step.detail}</p>
                  )}
                  {step.status === "done" && step.detail && (
                    <p className="truncate text-[11px] text-green-600">{step.detail}</p>
                  )}
                  {step.status === "done" && !step.detail && (
                    <p className="text-[11px] text-green-600">Concluído</p>
                  )}
                  {step.status === "idle" && (
                    <p className="text-[11px] text-muted-foreground/50">Aguardando...</p>
                  )}
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

