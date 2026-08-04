"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, ExternalLink, Search } from "lucide-react";
import Link from "next/link";
import { useDeferredValue, useState } from "react";

import { ApiErrorState, InsufficientData } from "@/components/feedback";
import { StartupLogo } from "@/components/startup-logo";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { getStartups } from "@/lib/api";
import { statusMeta } from "@/lib/status";
import type { NvidiaRecommendationItem, Startup } from "@/lib/types";
import { formatDate, formatNumber } from "@/lib/utils";

const PAGE_SIZE = 10;

export function RecommendationsPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search.trim());

  const query = useQuery({
    queryKey: ["startups", "with-nvidia-recommendations", page, deferredSearch],
    queryFn: ({ signal }) =>
      getStartups(
        {
          page,
          pageSize: PAGE_SIZE,
          search: deferredSearch || undefined,
          hasNvidiaRecommendation: true
        },
        signal
      ),
    placeholderData: (previous) => previous
  });

  const totalPages = Math.max(1, Math.ceil((query.data?.total || 0) / PAGE_SIZE));

  return (
    <main className="mx-auto w-full min-w-0 max-w-[1500px] px-4 py-6 lg:px-8">
      <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-medium text-primary">Recomendações NVIDIA</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">
            Empresas com recomendações
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Lista somente startups que já possuem recomendações NVIDIA salvas na
            plataforma.
          </p>
        </div>
        <label className="relative w-full sm:w-[320px]">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Buscar empresa recomendada..."
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
          />
        </label>
      </div>

      <Card className="overflow-hidden">
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="flex items-center gap-2">
            <h2 className="font-semibold">Recomendações geradas</h2>
            <Badge className="bg-white/[0.04] text-muted-foreground">
              {formatNumber(query.data?.total)}
            </Badge>
          </div>
        </div>

        {query.isError ? (
          <ApiErrorState
            message={
              query.error instanceof Error
                ? query.error.message
                : "Falha ao consultar recomendações."
            }
            onRetry={() => query.refetch()}
          />
        ) : query.isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton className="h-20 w-full" key={index} />
            ))}
          </div>
        ) : query.data?.items.length === 0 ? (
          <InsufficientData message="Nenhuma empresa com recomendação NVIDIA salva." />
        ) : (
          <div className="divide-y divide-border">
            {query.data?.items.map((startup) => (
              <RecommendationRow key={String(startup.id || startup.candidate_id)} startup={startup} />
            ))}
          </div>
        )}

        <div className="flex items-center justify-between border-t border-border px-4 py-3 text-xs text-muted-foreground">
          <span>
            {query.data?.total
              ? `Página ${page} de ${totalPages} · ${formatNumber(query.data.total)} empresas`
              : "Nenhuma empresa"}
          </span>
          <div className="flex gap-1">
            <Button
              aria-label="Página anterior"
              disabled={page <= 1 || query.isFetching}
              size="icon"
              variant="ghost"
              onClick={() => setPage((current) => current - 1)}
            >
              <ChevronLeft className="size-4" />
            </Button>
            <Button
              aria-label="Próxima página"
              disabled={page >= totalPages || query.isFetching}
              size="icon"
              variant="ghost"
              onClick={() => setPage((current) => current + 1)}
            >
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      </Card>
    </main>
  );
}

function RecommendationRow({ startup }: { startup: Startup }) {
  const id = String(startup.id || startup.candidate_id || "");
  const recommendation = startup.nvidia_recommendation;
  const recommendations = recommendationItems(recommendation?.recommendations);
  const products = recommendations
    .map((item) => item.produto)
    .filter((item): item is string => Boolean(item));
  const summary =
    recommendations[0]?.justificativa ||
    recommendation?.final_answer ||
    recommendation?.recommendation ||
    "Recomendação salva sem justificativa estruturada.";
  const status = statusMeta(startup.validation_status);

  return (
    <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1.6fr)_auto] lg:items-center">
      <div className="flex min-w-0 items-center gap-3">
        <StartupLogo
          className="size-10"
          website={startup.validated_url || startup.website}
          name={startup.company_name}
        />
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">
            {startup.company_name || "Empresa não informada"}
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <Badge className={status.className}>{status.label}</Badge>
            {startup.updated_at && (
              <span className="text-[11px] text-muted-foreground">
                Atualizada em {formatDate(startup.updated_at)}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="min-w-0">
        <div className="flex flex-wrap gap-1.5">
          {products.length ? (
            products.slice(0, 4).map((product) => (
              <Badge className="bg-primary/10 text-primary" key={product}>
                {product}
              </Badge>
            ))
          ) : (
            <Badge className="text-muted-foreground">Produto não estruturado</Badge>
          )}
          {products.length > 4 && <Badge>+{products.length - 4}</Badge>}
        </div>
        <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">
          {summary}
        </p>
      </div>

      <Button asChild size="sm" variant="outline">
        <Link href={`/startups/${encodeURIComponent(id)}`}>
          <ExternalLink className="mr-2 size-3.5" />
          Abrir
        </Link>
      </Button>
    </div>
  );
}

function recommendationItems(value: unknown): NvidiaRecommendationItem[] {
  return Array.isArray(value)
    ? value.filter((item): item is NvidiaRecommendationItem => Boolean(item) && typeof item === "object")
    : [];
}
