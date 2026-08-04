import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ScoreBar,
  MaturityBadge,
  CompanyLogo,
  ContactStatusBadge,
} from "@/components/ui-bits";
import { useContacts } from "@/lib/contacts-store";
import { useHealth } from "@/lib/hooks/use-health";
import { useStartups } from "@/lib/hooks/use-startups";
import { ApiErrorDisplay } from "@/components/api-error-display";
import { downloadCsv } from "@/lib/export-csv";
import { cn } from "@/lib/utils";
import type { ApiError, StartupRecord } from "@/lib/api";
import type { AIMaturity } from "@/lib/mock-data";
import {
  ArrowRight,
  Filter,
  Download,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from "lucide-react";

export const Route = createFileRoute("/ranking")({
  head: () => ({ meta: [{ title: "Ranking — NVIDIA Toph" }] }),
  component: Ranking,
});

function FilterGroup({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-b border-border pb-3 last:border-0">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </p>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

function CheckRow<T extends string>({
  value,
  label,
  set,
  current,
}: {
  value: T;
  label?: string;
  set: (v: T[]) => void;
  current: T[];
}) {
  const checked = current.includes(value);
  return (
    <label className="flex cursor-pointer items-center gap-2 text-xs text-foreground">
      <Checkbox
        checked={checked}
        onCheckedChange={() =>
          set(
            checked ? current.filter((v) => v !== value) : [...current, value],
          )
        }
      />
      <span className="truncate">{label ?? value}</span>
    </label>
  );
}

function scoreFromCount(count: number, max: number): number {
  return Math.round(Math.min(count / max, 1) * 100);
}

function ThSort({
  field,
  label,
  sortField,
  sortDir,
  onToggle,
}: {
  field: SortField;
  label: string;
  sortField: SortField;
  sortDir: SortDir;
  onToggle: (f: SortField) => void;
}) {
  const isActive = sortField === field;
  const Icon = isActive
    ? sortDir === "asc"
      ? ArrowUp
      : ArrowDown
    : ArrowUpDown;
  return (
    <th className="px-3 py-2 font-medium">
      <button
        className="inline-flex items-center gap-1 text-[11px] uppercase tracking-wider text-muted-foreground hover:text-foreground"
        onClick={() => onToggle(field)}
      >
        {label}
        <Icon
          className={cn("h-3 w-3", isActive ? "text-primary" : "opacity-40")}
        />
      </button>
    </th>
  );
}

type SortField =
  | "name"
  | "sector"
  | "classification_label"
  | "radar_score"
  | "evidence_count"
  | "recommendation_count";
type SortDir = "asc" | "desc";

function isAIMaturity(value: string | null): value is AIMaturity {
  return value === "AI-Native" || value === "AI-Enabled" || value === "Non-AI";
}

function Ranking() {
  const contacts = useContacts();
  const {
    data: health,
    error: healthError,
    refetch: retryHealth,
  } = useHealth();
  const {
    data: startupRecords = [],
    isLoading: startupsLoading,
    error: startupsError,
  } = useStartups();
  const [search, setSearch] = useState("");
  const [maturity, setMaturity] = useState<string[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [sortField, setSortField] = useState<SortField>("radar_score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);

  const records = startupRecords as StartupRecord[];

  const sectorsList = useMemo(
    () =>
      Array.from(
        new Set(
          records
            .map((s) => s.sector)
            .filter((sector): sector is string => Boolean(sector)),
        ),
      ),
    [records],
  );
  const maturitiesList = ["AI-Native", "AI-Enabled", "Non-AI"];

  const filtered = useMemo(() => {
    return records.filter((s) => {
      if (search && !s.name.toLowerCase().includes(search.toLowerCase()))
        return false;
      if (maturity.length && !maturity.includes(s.classification_label ?? ""))
        return false;
      if (sectors.length && !sectors.includes(s.sector ?? "")) return false;
      return true;
    });
  }, [search, maturity, sectors, records]);

  const sorted = useMemo(() => {
    const collator = new Intl.Collator("pt-BR", { sensitivity: "base" });
    return [...filtered].sort((a, b) => {
      const av = a[sortField];
      const bv = b[sortField];
      let cmp: number;
      if (typeof av === "number" && typeof bv === "number") {
        cmp = av - bv;
      } else {
        cmp = collator.compare(String(av ?? ""), String(bv ?? ""));
      }
      return sortDir === "desc" ? -cmp : cmp;
    });
  }, [filtered, sortField, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const paginated = useMemo(() => {
    const start = page * pageSize;
    return sorted.slice(start, start + pageSize);
  }, [sorted, page, pageSize]);

  const toggleSort = useCallback((field: SortField) => {
    setSortField((prev) => {
      if (prev === field) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
        return field;
      }
      setSortDir("desc");
      return field;
    });
    setPage(0);
  }, []);

  function handleExportCsv() {
    const headers = [
      "Startup",
      "Setor",
      "Maturidade",
      "Contato",
      "Radar Score",
      "Evidências",
      "Recomendações",
      "Funding",
    ];
    const rows = filtered.map((s) => {
      const status = contacts[s.id]?.status ?? "Não contactada";
      return [
        s.name,
        s.sector ?? "",
        s.classification_label ?? "",
        status,
        s.radar_score ?? 0,
        s.evidence_count ?? 0,
        s.recommendation_count ?? 0,
        s.funding ?? "",
      ];
    });
    downloadCsv("ranking-startups", headers, rows);
  }

  const error = healthError ?? startupsError;
  if (error) {
    return (
      <div className="mx-auto w-full max-w-[1600px] p-4 md:p-6">
        <ApiErrorDisplay
          error={error as unknown as ApiError}
          onRetry={() => retryHealth()}
        />
      </div>
    );
  }

  if (!health || startupsLoading) {
    return (
      <div className="mx-auto w-full max-w-[1600px] p-4 md:p-6">
        <Card className="p-4">
          <div className="space-y-3">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto grid w-full max-w-[1600px] gap-4 p-4 md:p-6 lg:grid-cols-[220px_minmax(0,1fr)]">
      {/* Filters */}
      <Card className="h-fit p-4 lg:sticky lg:top-20">
        <div className="mb-3 flex items-center gap-2">
          <Filter className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-semibold text-foreground">Filtros</h2>
        </div>
        <ScrollArea className="h-[70vh] pr-3">
          <div className="space-y-4">
            <FilterGroup title="Maturidade de IA">
              {maturitiesList.map((m) => (
                <CheckRow
                  key={m}
                  value={m}
                  set={setMaturity}
                  current={maturity}
                />
              ))}
            </FilterGroup>
            <FilterGroup title="Setor">
              {sectorsList.map((s) => (
                <CheckRow
                  key={s}
                  value={s}
                  set={setSectors}
                  current={sectors}
                />
              ))}
              {sectorsList.length === 0 && (
                <p className="text-[11px] text-muted-foreground">
                  Nenhum setor disponível
                </p>
              )}
            </FilterGroup>
          </div>
        </ScrollArea>
      </Card>

      {/* Table */}
      <div className="min-w-0 space-y-3">
        <Card className="p-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(0);
              }}
              placeholder="Filtrar por nome…"
              className="h-9 sm:max-w-xs"
            />
            <div className="flex items-center gap-3">
              <Badge variant="outline" className="text-[11px]">
                {filtered.length} de {records.length}
              </Badge>
              <Button
                size="sm"
                variant="outline"
                className="gap-1.5 text-xs"
                onClick={handleExportCsv}
              >
                <Download className="h-3.5 w-3.5" /> CSV
              </Button>
            </div>
          </div>
        </Card>

        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] border-collapse text-sm">
              <thead className="bg-muted/50 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <ThSort
                    field="name"
                    label="Startup"
                    sortField={sortField}
                    sortDir={sortDir}
                    onToggle={toggleSort}
                  />
                  <ThSort
                    field="sector"
                    label="Setor"
                    sortField={sortField}
                    sortDir={sortDir}
                    onToggle={toggleSort}
                  />
                  <ThSort
                    field="classification_label"
                    label="AI maturity"
                    sortField={sortField}
                    sortDir={sortDir}
                    onToggle={toggleSort}
                  />
                  <th className="px-3 py-2 font-medium">Contato</th>
                  <ThSort
                    field="radar_score"
                    label="Radar"
                    sortField={sortField}
                    sortDir={sortDir}
                    onToggle={toggleSort}
                  />
                  <ThSort
                    field="evidence_count"
                    label="Evidências"
                    sortField={sortField}
                    sortDir={sortDir}
                    onToggle={toggleSort}
                  />
                  <ThSort
                    field="recommendation_count"
                    label="Recomendações"
                    sortField={sortField}
                    sortDir={sortDir}
                    onToggle={toggleSort}
                  />
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {paginated.map((s) => {
                  const status = contacts[s.id]?.status ?? "Não contactada";
                  const evidenceScore = scoreFromCount(
                    s.evidence_count ?? 0,
                    5,
                  );
                  const recScore = scoreFromCount(
                    s.recommendation_count ?? 0,
                    3,
                  );
                  return (
                    <tr
                      key={s.id}
                      className="border-t border-border hover:bg-muted/30"
                    >
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-2.5">
                          <Link
                            to="/startup/$id"
                            params={{ id: s.id }}
                            aria-label={`Abrir perfil de ${s.name}`}
                            className="rounded-md outline-none ring-primary/40 transition hover:opacity-85 focus-visible:ring-2"
                          >
                            <CompanyLogo id={s.id} name={s.name} size="sm" />
                          </Link>
                          <div className="min-w-0">
                            <div className="truncate font-medium text-foreground">
                              {s.name}
                            </div>
                            <div className="truncate text-[11px] text-muted-foreground">
                              {s.funding || "—"}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-2.5 text-xs text-foreground">
                        {s.sector || "—"}
                      </td>
                      <td className="px-3 py-2.5">
                        {isAIMaturity(s.classification_label) ? (
                          <MaturityBadge value={s.classification_label} />
                        ) : (
                          <span className="text-xs text-muted-foreground">
                            —
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2.5">
                        <ContactStatusBadge status={status} />
                      </td>
                      <td className="px-3 py-2.5 w-36">
                        <ScoreBar value={s.radar_score ?? 0} />
                      </td>
                      <td className="px-3 py-2.5 w-36">
                        <ScoreBar value={evidenceScore} />
                      </td>
                      <td className="px-3 py-2.5 w-36">
                        <ScoreBar value={recScore} />
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <Button
                          asChild
                          size="sm"
                          variant="ghost"
                          className="gap-1 text-xs"
                        >
                          <Link to="/startup/$id" params={{ id: s.id }}>
                            Ver <ArrowRight className="h-3 w-3" />
                          </Link>
                        </Button>
                      </td>
                    </tr>
                  );
                })}
                {paginated.length === 0 && (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-3 py-10 text-center text-xs text-muted-foreground"
                    >
                      Nenhuma startup com os filtros atuais.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Pagination */}
        {totalPages > 1 && (
          <Card className="flex flex-wrap items-center justify-between gap-3 p-3">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>Linhas por página:</span>
              <Select
                value={String(pageSize)}
                onValueChange={(v) => {
                  setPageSize(Number(v));
                  setPage(0);
                }}
              >
                <SelectTrigger className="h-7 w-16 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">10</SelectItem>
                  <SelectItem value="25">25</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-1 text-xs">
              <Button
                size="sm"
                variant="outline"
                className="h-7 px-2"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                Anterior
              </Button>
              {Array.from({ length: totalPages }, (_, i) => (
                <Button
                  key={i}
                  size="sm"
                  variant={i === page ? "default" : "outline"}
                  className="h-7 min-w-7 px-1 text-xs"
                  onClick={() => setPage(i)}
                >
                  {i + 1}
                </Button>
              ))}
              <Button
                size="sm"
                variant="outline"
                className="h-7 px-2"
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              >
                Próximo
              </Button>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
