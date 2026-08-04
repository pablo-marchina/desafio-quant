"use client";

import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

import { AutomationRegistrationsChart } from "@/components/automation-registrations-chart";
import { ApiErrorState } from "@/components/feedback";
import { StartupsTable } from "@/components/startups-table";
import { StatusChart } from "@/components/status-chart";
import { SummaryCards } from "@/components/summary-cards";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getDashboardSummary } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export function Dashboard() {
  const summaryQuery = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: ({ signal }) => getDashboardSummary(signal),
    refetchInterval: 60_000
  });

  return (
    <main className="mx-auto w-full min-w-0 max-w-[1500px] overflow-x-hidden px-4 py-6 lg:px-8">
      <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Visão Geral</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Acompanhe a captura, validação e enriquecimento de startups.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {summaryQuery.data && (
            <span className="hidden text-[11px] text-muted-foreground sm:inline">
              Atualizado em {formatDate(summaryQuery.data.generated_at)}
            </span>
          )}
          <Button
            size="sm"
            variant="outline"
            disabled={summaryQuery.isFetching}
            onClick={() => summaryQuery.refetch()}
          >
            <RefreshCw
              className={`mr-2 size-3.5 ${summaryQuery.isFetching ? "animate-spin" : ""}`}
            />
            Atualizar
          </Button>
        </div>
      </div>

      <div className="space-y-3">
        {summaryQuery.isError ? (
          <Card>
            <ApiErrorState
              message={
                summaryQuery.error instanceof Error
                  ? summaryQuery.error.message
                  : "Falha ao consultar o resumo."
              }
              onRetry={() => summaryQuery.refetch()}
            />
          </Card>
        ) : (
          <>
            <SummaryCards
              summary={summaryQuery.data}
              loading={summaryQuery.isLoading}
            />
            <AutomationRegistrationsChart
              summary={summaryQuery.data}
              loading={summaryQuery.isLoading}
            />
          </>
        )}
        <StartupsTable />
        <StatusChart summary={summaryQuery.data} loading={summaryQuery.isLoading} />
      </div>
    </main>
  );
}
