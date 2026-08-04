import { createFileRoute } from "@tanstack/react-router";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ScoreBar } from "@/components/ui-bits";
import { useMemo, useState } from "react";
import { useHealth } from "@/lib/hooks/use-health";
import { useSources } from "@/lib/hooks/use-sources";
import { ApiErrorDisplay } from "@/components/api-error-display";
import { downloadCsv } from "@/lib/export-csv";
import { cn } from "@/lib/utils";
import { Database, Download, Search } from "lucide-react";
import type { ApiError, SourceDocumentRecord } from "@/lib/api";

export const Route = createFileRoute("/sources")({
  head: () => ({ meta: [{ title: "Fontes & Evidências — NVIDIA Toph" }] }),
  component: SourcesPage,
});

type SourceStatus = "forte" | "média" | "fraca" | "sem evidências";

function confidenceScore(source: SourceDocumentRecord): number {
  const confidence = source.average_claim_confidence ?? 0;
  return Math.round(Math.min(1, Math.max(0, confidence)) * 100);
}

function sourceStatus(source: SourceDocumentRecord): SourceStatus {
  if (source.claim_count === 0) return "sem evidências";
  const score = confidenceScore(source);
  if (score >= 75) return "forte";
  if (score >= 50) return "média";
  return "fraca";
}

function statusClass(status: SourceStatus): string {
  const map: Record<SourceStatus, string> = {
    forte: "bg-primary",
    média: "bg-info",
    fraca: "bg-warning",
    "sem evidências": "bg-muted-foreground/60",
  };
  return map[status];
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function SourcesPage() {
  const [q, setQ] = useState("");
  const {
    data: health,
    error: healthError,
    refetch: retryHealth,
  } = useHealth();
  const {
    data: sources = [],
    error: sourcesError,
    isLoading: sourcesLoading,
    refetch: retrySources,
  } = useSources();

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();
    if (!query) return sources;
    return sources.filter((source) => {
      const haystack = [
        source.domain,
        source.url,
        source.title ?? "",
        source.source_type,
        source.collection_method,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [q, sources]);

  const summary = useMemo(() => {
    const withClaims = sources.filter(
      (source) => source.claim_count > 0,
    ).length;
    const needsReview = sources.filter(
      (source) => source.claim_count === 0 || sourceStatus(source) === "fraca",
    ).length;
    const totalClaims = sources.reduce(
      (sum, source) => sum + source.claim_count,
      0,
    );
    return { total: sources.length, withClaims, needsReview, totalClaims };
  }, [sources]);

  function handleExportCsv() {
    const headers = [
      "Domínio",
      "URL",
      "Título",
      "Tipo",
      "Claims",
      "Confiança Média",
      "Coleta",
      "Status",
    ];
    const rows = sources.map((s) => {
      const status = sourceStatus(s);
      return [
        s.domain,
        s.url,
        s.title ?? "",
        s.source_type,
        s.claim_count,
        confidenceScore(s),
        formatDate(s.retrieved_at),
        status,
      ];
    });
    downloadCsv("fontes-evidencias", headers, rows);
  }

  const error = healthError ?? sourcesError;
  if (error) {
    return (
      <div className="mx-auto w-full max-w-7xl p-4 md:p-6">
        <ApiErrorDisplay
          error={error as unknown as ApiError}
          onRetry={() => (healthError ? retryHealth() : retrySources())}
        />
      </div>
    );
  }

  if (!health || sourcesLoading) {
    return (
      <div className="mx-auto w-full max-w-7xl p-4 md:p-6">
        <Card className="p-4">
          <div className="space-y-3">
            <Skeleton className="h-5 w-48" />
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-20" />
              ))}
            </div>
            <Skeleton className="h-64 w-full" />
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-5 p-4 md:p-6">
      <div>
        <h1 className="text-lg font-semibold text-foreground">
          Fontes & Evidências
        </h1>
        <p className="text-xs text-muted-foreground">
          Auditoria das fontes coletadas e claims persistidos pelo pipeline.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Card className="p-3">
          <p className="text-[10px] uppercase text-muted-foreground">Fontes</p>
          <p className="text-xl font-semibold tabular-nums">{summary.total}</p>
        </Card>
        <Card className="p-3">
          <p className="text-[10px] uppercase text-muted-foreground">
            Com claims
          </p>
          <p className="text-xl font-semibold tabular-nums text-primary">
            {summary.withClaims}
          </p>
        </Card>
        <Card className="p-3">
          <p className="text-[10px] uppercase text-muted-foreground">Claims</p>
          <p className="text-xl font-semibold tabular-nums text-info">
            {summary.totalClaims}
          </p>
        </Card>
        <Card className="p-3">
          <p className="text-[10px] uppercase text-muted-foreground">Revisar</p>
          <p className="text-xl font-semibold tabular-nums text-warning">
            {summary.needsReview}
          </p>
        </Card>
      </div>

      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative max-w-md grow">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Filtrar fontes por domínio, URL ou tipo..."
              className="h-9 pl-8"
            />
          </div>
          <Button
            size="sm"
            variant="outline"
            className="gap-1.5 text-xs"
            onClick={handleExportCsv}
          >
            <Download className="h-3.5 w-3.5" /> CSV
          </Button>
        </div>
      </Card>

      {sources.length === 0 ? (
        <Card className="flex min-h-64 flex-col items-center justify-center gap-3 p-6 text-center">
          <div className="grid h-10 w-10 place-items-center rounded-md bg-muted text-muted-foreground">
            <Database className="h-5 w-5" />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium text-foreground">
              Nenhuma fonte persistida ainda
            </p>
            <p className="max-w-md text-xs text-muted-foreground">
              Execute uma análise na tela Pipeline para gravar fontes e
              evidências no backend local.
            </p>
          </div>
        </Card>
      ) : (
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[880px] border-collapse text-sm">
              <thead className="bg-muted/50 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Fonte</th>
                  <th className="px-3 py-2 font-medium">Tipo</th>
                  <th className="px-3 py-2 font-medium">Claims</th>
                  <th className="px-3 py-2 font-medium">Confiança média</th>
                  <th className="px-3 py-2 font-medium">Coleta</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((source) => {
                  const status = sourceStatus(source);
                  return (
                    <tr
                      key={source.id}
                      className="border-t border-border hover:bg-muted/30"
                    >
                      <td className="max-w-sm px-3 py-2.5">
                        <div className="min-w-0 space-y-1">
                          <code className="block truncate text-xs text-foreground">
                            {source.domain}
                          </code>
                          <a
                            className="block truncate text-[11px] text-muted-foreground hover:text-primary"
                            href={source.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {source.title || source.url}
                          </a>
                        </div>
                      </td>
                      <td className="px-3 py-2.5 text-xs text-foreground">
                        {source.source_type}
                      </td>
                      <td className="px-3 py-2.5 text-xs tabular-nums text-foreground">
                        {source.claim_count}
                      </td>
                      <td className="w-48 px-3 py-2.5">
                        <ScoreBar value={confidenceScore(source)} />
                      </td>
                      <td className="px-3 py-2.5 text-xs tabular-nums text-muted-foreground">
                        {formatDate(source.retrieved_at)}
                      </td>
                      <td className="px-3 py-2.5">
                        <Badge
                          variant="outline"
                          className="gap-1.5 text-[10px] capitalize"
                        >
                          <span
                            className={cn(
                              "inline-block h-2 w-2 rounded-full",
                              statusClass(status),
                            )}
                          />{" "}
                          {status}
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
