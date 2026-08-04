import { CheckCircle2 } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { DashboardSummary } from "@/lib/types";
import { formatNumber } from "@/lib/utils";

export function Pipeline({
  summary,
  loading
}: {
  summary?: DashboardSummary;
  loading: boolean;
}) {
  const approved = summary?.validation_statuses.APPROVED || 0;
  const enriched = summary?.enrichment_statuses.enriched || 0;
  const progress = approved ? Math.min(100, Math.round((enriched / approved) * 100)) : 0;
  const steps = [
    ["Coleta", summary?.total_startups],
    ["Validação", approved],
    ["Limpeza", approved],
    ["Enriquecimento", enriched],
    ["Conclusão", enriched]
  ] as const;

  return (
    <Card className="p-4">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center">
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold">Pipeline de enriquecimento</h2>
          {loading ? (
            <Skeleton className="mt-6 h-12 w-full" />
          ) : (
            <div className="mt-5 grid grid-cols-5">
              {steps.map(([label, value], index) => (
                <div className="relative text-center" key={label}>
                  {index < steps.length - 1 && (
                    <div className="absolute left-1/2 top-2 h-px w-full bg-primary/60" />
                  )}
                  <div className="relative z-10 mx-auto grid size-5 place-items-center rounded-full border border-primary bg-card text-primary">
                    <CheckCircle2 className="size-3" />
                  </div>
                  <p className="mt-2 truncate px-1 text-[11px] text-muted-foreground">
                    {label}
                  </p>
                  <p className="mt-1 text-xs">{formatNumber(value)}</p>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="w-full rounded-lg border border-border bg-white/[0.025] p-4 lg:w-48">
          <p className="text-xs text-muted-foreground">Progresso geral</p>
          {loading ? (
            <Skeleton className="mt-2 h-7 w-20" />
          ) : (
            <>
              <p className="mt-1 text-2xl font-semibold">{approved ? `${progress}%` : "—"}</p>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                <div className="h-full rounded-full bg-primary" style={{ width: `${progress}%` }} />
              </div>
              <p className="mt-2 text-[10px] text-muted-foreground">
                {approved
                  ? `${formatNumber(enriched)} de ${formatNumber(approved)} aprovadas`
                  : "Dados insuficientes"}
              </p>
            </>
          )}
        </div>
      </div>
    </Card>
  );
}
