"use client";

import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable
} from "@tanstack/react-table";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Filter,
  Search
} from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";

import { ApiErrorState, InsufficientData } from "@/components/feedback";
import { StartupLogo } from "@/components/startup-logo";
import { StartupDetails } from "@/components/startup-details";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { getStartups } from "@/lib/api";
import { displayStartupAiLabel, statusMeta, toStringList } from "@/lib/status";
import type { Startup } from "@/lib/types";
import { formatDate, formatNumber, getDomain } from "@/lib/utils";

const PAGE_SIZE = 5;

export function StartupsTable() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<Startup | null>(null);
  const deferredSearch = useDeferredValue(search.trim());

  const query = useQuery({
    queryKey: ["startups", page, deferredSearch, status],
    queryFn: ({ signal }) =>
      getStartups(
        {
          page,
          pageSize: PAGE_SIZE,
          search: deferredSearch || undefined,
          validationStatus: status || undefined
        },
        signal
      ),
    placeholderData: (previous) => previous
  });

  const columns = useMemo<ColumnDef<Startup>[]>(
    () => [
      {
        accessorKey: "company_name",
        header: "Startup",
        cell: ({ row }) => (
          <div className="flex min-w-[150px] items-center gap-2.5">
            <StartupLogo
              className="size-8"
              website={row.original.validated_url || row.original.website}
              name={row.original.company_name}
            />
            <span className="truncate font-medium">
              {row.original.company_name || "Não informado"}
            </span>
          </div>
        )
      },
      {
        id: "domain",
        header: "Domínio",
        cell: ({ row }) => (
          <span className="text-muted-foreground">
            {getDomain(row.original.validated_url || row.original.website)}
          </span>
        )
      },
      {
        accessorKey: "validation_status",
        header: "Status",
        cell: ({ getValue }) => {
          const meta = statusMeta(getValue<string | undefined>());
          return <Badge className={meta.className}>{meta.label}</Badge>;
        }
      },
      {
        accessorKey: "ai_dependency_level",
        header: "Classificação de IA",
        cell: ({ row }) => {
          return (
            <span className="text-muted-foreground">
              {displayStartupAiLabel(row.original)}
            </span>
          );
        }
      },
      {
        accessorKey: "tech_stack",
        header: "Stack tecnológica",
        cell: ({ getValue }) => {
          const values = toStringList(getValue<string[] | string | null>());
          return values.length ? (
            <div className="flex min-w-[180px] gap-1">
              {values.slice(0, 3).map((tech) => (
                <Badge className="bg-white/[0.025] text-foreground" key={tech}>
                  {tech}
                </Badge>
              ))}
              {values.length > 3 && <Badge>+{values.length - 3}</Badge>}
            </div>
          ) : (
            <span className="text-muted-foreground">Dados insuficientes</span>
          );
        }
      },
      {
        accessorKey: "updated_at",
        header: "Atualizado em",
        cell: ({ getValue }) => (
          <span className="whitespace-nowrap text-muted-foreground">
            {formatDate(getValue<string | null>())}
          </span>
        )
      }
    ],
    []
  );

  const table = useReactTable({
    data: query.data?.items || [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true
  });
  const totalPages = Math.max(1, Math.ceil((query.data?.total || 0) / PAGE_SIZE));

  return (
    <>
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-border p-4 md:flex-row md:items-center">
          <div className="flex items-center gap-2">
            <h2 className="font-semibold">Startups</h2>
            <Badge className="bg-white/[0.04] text-muted-foreground">
              {formatNumber(query.data?.total)}
            </Badge>
          </div>
          <div className="flex flex-1 flex-col gap-2 sm:flex-row md:justify-end">
            <label className="relative w-full sm:w-[260px]">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                className="pl-9"
                placeholder="Buscar na tabela..."
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setPage(1);
                }}
              />
            </label>
            <label className="relative">
              <Filter className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <select
                aria-label="Filtrar por status"
                className="h-9 min-w-40 rounded-md border border-border bg-background pl-9 pr-8 text-xs outline-none focus:border-primary/50"
                value={status}
                onChange={(event) => {
                  setStatus(event.target.value);
                  setPage(1);
                }}
              >
                <option value="">Todos os status</option>
                <option value="APPROVED">Aprovadas</option>
                <option value="REVIEW">Em revisão</option>
                <option value="REJECTED">Rejeitadas</option>
                <option value="DISCARDED">Descartadas</option>
              </select>
            </label>
          </div>
        </div>

        {query.isError ? (
          <ApiErrorState
            message={
              query.error instanceof Error
                ? query.error.message
                : "Falha ao consultar startups."
            }
            onRetry={() => query.refetch()}
          />
        ) : query.isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 5 }).map((_, index) => (
              <Skeleton className="h-12 w-full" key={index} />
            ))}
          </div>
        ) : query.data?.items.length === 0 ? (
          <InsufficientData message="Nenhuma startup encontrada com os filtros aplicados." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-border bg-white/[0.015] text-muted-foreground">
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <th className="whitespace-nowrap px-4 py-3 font-medium" key={header.id}>
                        {flexRender(header.column.columnDef.header, header.getContext())}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <tr
                    className="cursor-pointer border-b border-border/60 transition last:border-0 hover:bg-white/[0.025]"
                    key={row.id}
                    onClick={() => setSelected(row.original)}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td className="px-4 py-3" key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex items-center justify-between border-t border-border px-4 py-3 text-xs text-muted-foreground">
          <span>
            {query.data?.total
              ? `Página ${page} de ${totalPages} · ${formatNumber(query.data.total)} resultados`
              : "Nenhum resultado"}
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
      {selected && <StartupDetails startup={selected} onClose={() => setSelected(null)} />}
    </>
  );
}
