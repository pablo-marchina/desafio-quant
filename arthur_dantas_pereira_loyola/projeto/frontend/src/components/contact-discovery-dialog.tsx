import { useEffect, useRef, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import {
  Loader2,
  CheckCircle2,
  XCircle,
  Search,
  Globe,
  Mail,
  Database,
  GitCompare,
  Save,
} from "lucide-react";
import { cn } from "@/lib/utils";

type StepStatus = "idle" | "running" | "done" | "error";

interface StepData {
  key: string;
  status: StepStatus;
  detail?: string;
  error_message?: string;
}

const CONTACT_STEPS = [
  { key: "preparing_queries", name: "Preparando queries", icon: Search },
  { key: "searching_web", name: "Buscando paginas", icon: Globe },
  { key: "extracting_contacts", name: "Extraindo contatos", icon: Mail },
  { key: "fallback_sources", name: "Fontes existentes", icon: Database },
  { key: "cross_referencing", name: "Cruzando referencias", icon: GitCompare },
  { key: "saving_result", name: "Salvando resultado", icon: Save },
];

interface ContactDiscoveryDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  startupId: string;
  apiBase: string;
  onComplete: () => void;
}

export function ContactDiscoveryDialog({
  open,
  onOpenChange,
  startupId,
  apiBase,
  onComplete,
}: ContactDiscoveryDialogProps) {
  const [steps, setSteps] = useState<StepData[]>(
    CONTACT_STEPS.map((s) => ({ key: s.key, status: "idle" })),
  );
  const [overallStatus, setOverallStatus] = useState<
    "pending" | "completed" | "error"
  >("pending");
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!open || !startupId) return;

    setSteps(CONTACT_STEPS.map((s) => ({ key: s.key, status: "idle" })));
    setOverallStatus("pending");

    const doDiscover = async () => {
      try {
        const res = await fetch(`${apiBase}/startups/${startupId}/contacts`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });
        if (!res.ok) {
          setOverallStatus("error");
          return;
        }
        const data = await res.json();
        if (data.cached) {
          setSteps(
            CONTACT_STEPS.map((s) => ({ key: s.key, status: "done" })),
          );
          setOverallStatus("completed");
          onComplete();
          return;
        }

        const es = new EventSource(
          `${apiBase}/startups/${startupId}/contacts/stream`,
        );
        eventSourceRef.current = es;

        es.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as StepData[];
            setSteps(data);
          } catch {}
        };

        es.addEventListener("done", () => {
          es.close();
          setOverallStatus("completed");
          onComplete();
        });

        es.onerror = () => {
          setOverallStatus("error");
          es.close();
        };
      } catch {
        setOverallStatus("error");
      }
    };

    doDiscover();

    return () => {
      eventSourceRef.current?.close();
    };
  }, [open, startupId, apiBase, onComplete]);

  const doneCount = steps.filter((s) => s.status === "done").length;
  const errorCount = steps.filter((s) => s.status === "error").length;
  const total = steps.length;
  const progress =
    overallStatus === "completed"
      ? 100
      : Math.round((doneCount / total) * 100);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Buscando contatos</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex items-center justify-between gap-2">
            {overallStatus === "pending" && (
              <Badge className="animate-pulse gap-1.5 bg-primary text-primary-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />{" "}
                Processando...
              </Badge>
            )}
            {overallStatus === "completed" && (
              <Badge className="gap-1.5 bg-green-600 text-white">
                <CheckCircle2 className="h-3.5 w-3.5" />{" "}
                {errorCount > 0 ? "Concluido com erros" : "Concluido"}
              </Badge>
            )}
            {overallStatus === "error" && (
              <Badge className="gap-1.5 bg-destructive text-destructive-foreground">
                <XCircle className="h-3.5 w-3.5" /> Falhou
              </Badge>
            )}
          </div>

          <Progress value={progress} className="h-2" />

          <div className="space-y-2">
            {CONTACT_STEPS.map((def) => {
              const step = steps.find((s) => s.key === def.key);
              const status = step?.status ?? "idle";
              const Icon = def.icon;

              return (
                <div
                  key={def.key}
                  className={cn(
                    "flex items-center gap-3 rounded-md border p-3 transition-all",
                    status === "running" && "border-primary/50 ring-1 ring-primary/20",
                    status === "error" && "border-destructive/50",
                    status === "done" && "border-green-500/30",
                    status === "idle" && "border-border opacity-50",
                  )}
                >
                  <div
                    className={cn(
                      "grid h-8 w-8 shrink-0 place-items-center rounded-md",
                      status === "running" && "bg-primary/10",
                      status === "done" && "bg-green-500/10",
                      status === "error" && "bg-destructive/10",
                      status === "idle" && "bg-muted",
                    )}
                  >
                    {status === "running" && (
                      <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    )}
                    {status === "done" && (
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                    )}
                    {status === "error" && (
                      <XCircle className="h-4 w-4 text-destructive" />
                    )}
                    {status === "idle" && (
                      <Icon className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">
                      {def.name}
                    </p>
                    {status === "running" && step?.detail && (
                      <p className="animate-pulse truncate text-[11px] text-muted-foreground">
                        {step.detail}
                      </p>
                    )}
                    {status === "running" && !step?.detail && (
                      <p className="animate-pulse text-[11px] text-muted-foreground">
                        Em andamento...
                      </p>
                    )}
                    {status === "error" && (
                      <p className="truncate text-[11px] text-destructive">
                        {step?.error_message || step?.detail || "Falhou"}
                      </p>
                    )}
                    {status === "done" && (
                      <p className="truncate text-[11px] text-green-600">
                        {step?.detail || "Concluido"}
                      </p>
                    )}
                    {status === "idle" && (
                      <p className="text-[11px] text-muted-foreground/50">
                        Aguardando...
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
