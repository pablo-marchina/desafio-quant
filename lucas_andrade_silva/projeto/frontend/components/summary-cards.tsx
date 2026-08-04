import {
  CheckCircle2,
  Clock3,
  Database,
  Cpu,
  XCircle
} from "lucide-react";
import Link from "next/link";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { DashboardSummary } from "@/lib/types";
import { cn, formatNumber } from "@/lib/utils";

type Props = {
  summary?: DashboardSummary;
  loading: boolean;
};

export function SummaryCards({ summary, loading }: Props) {
  const validation = summary?.validation_statuses || {};
  const cards = [
    {
      label: "Startups capturadas",
      value: summary?.total_startups,
      note: "Total registrado pela API",
      icon: Database,
      color: "text-primary",
      bg: "bg-primary/10"
    },
    {
      label: "Validadas (aprovadas)",
      value: validation.APPROVED || 0,
      note: percentage(validation.APPROVED, summary?.total_startups),
      icon: CheckCircle2,
      color: "text-primary",
      bg: "bg-primary/10"
    },
    {
      label: "Em revisão",
      value: validation.REVIEW || 0,
      note: percentage(validation.REVIEW, summary?.total_startups),
      icon: Clock3,
      color: "text-warning",
      bg: "bg-warning/10"
    },
    {
      label: "Descartadas",
      value: (validation.DISCARDED || 0) + (validation.REJECTED || 0),
      note: percentage(
        (validation.DISCARDED || 0) + (validation.REJECTED || 0),
        summary?.total_startups
      ),
      icon: XCircle,
      color: "text-destructive",
      bg: "bg-destructive/10"
    },
    {
      label: "Recomendações",
      value: summary?.recommendations_count || 0,
      note: percentage(summary?.recommendations_count, summary?.total_startups),
      icon: Cpu,
      color: "text-primary",
      bg: "bg-primary/10",
      href: "/recomendacoes"
    }
  ];

  return (
    <div className="grid min-w-0 auto-rows-fr gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
      {cards.map(({ label, value, note, icon: Icon, color, bg, href }) => {
        const content = (
          <Card
            className={cn(
              "relative min-w-0 overflow-hidden p-4",
              href && "transition hover:border-primary/40 hover:bg-white/[0.025]"
            )}
          >
            <p className="pr-10 text-xs text-muted-foreground">{label}</p>
            {loading ? (
              <>
                <Skeleton className="mt-3 h-8 w-24" />
                <Skeleton className="mt-3 h-3 w-28" />
              </>
            ) : (
              <>
                <p className="mt-2 text-2xl font-semibold tracking-tight">
                  {formatNumber(value)}
                </p>
                <p className="mt-2 truncate text-[11px] text-muted-foreground">{note}</p>
              </>
            )}
            <div
              className={cn(
                "absolute right-4 top-1/2 grid size-9 -translate-y-1/2 place-items-center rounded-full",
                bg,
                color
              )}
            >
              <Icon className="size-[18px]" />
            </div>
          </Card>
        );
        return href ? (
          <Link className="block" href={href} key={label}>
            {content}
          </Link>
        ) : (
          <div key={label}>{content}</div>
        );
      })}
    </div>
  );
}

function percentage(value?: number, total?: number) {
  if (!total || value === undefined) return "Percentual indisponível";
  return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(
    (value / total) * 100
  )}% do total`;
}
