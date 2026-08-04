import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { ArrowRight, Handshake, Mail, Phone } from "lucide-react";
import { ApiErrorDisplay } from "@/components/api-error-display";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  CompanyLogo,
  ContactStatusBadge,
  SectionTitle,
} from "@/components/ui-bits";
import type { ApiError } from "@/lib/api";
import { formatDate, parseListField, unavailable } from "@/lib/api-derived";
import {
  CONTACT_STATUSES,
  setContactStatus,
  useContacts,
  type ContactStatus,
} from "@/lib/contacts-store";
import { useHealth } from "@/lib/hooks/use-health";
import { useStartups } from "@/lib/hooks/use-startups";

export const Route = createFileRoute("/contacts")({
  head: () => ({ meta: [{ title: "Contatos - NVIDIA Toph" }] }),
  component: ContactsPage,
});

const FILTERS: (ContactStatus | "Todas")[] = ["Todas", ...CONTACT_STATUSES];
const DEFAULT_STATUS = CONTACT_STATUSES[0];

function ContactsPage() {
  const contacts = useContacts();
  const healthQuery = useHealth();
  const startupsQuery = useStartups();
  const startups = useMemo(
    () => startupsQuery.data ?? [],
    [startupsQuery.data],
  );
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("Todas");

  const rows = useMemo(() => {
    const query = search.trim().toLowerCase();
    return startups
      .map((startup) => ({
        startup,
        rec: contacts[startup.id] ?? { status: DEFAULT_STATUS, updatedAt: "" },
      }))
      .filter(({ startup, rec }) => {
        if (filter !== "Todas" && rec.status !== filter) return false;
        if (!query) return true;
        const haystack = [
          startup.name,
          startup.sector ?? "",
          startup.product ?? "",
          startup.classification_label ?? "",
        ]
          .join(" ")
          .toLowerCase();
        return haystack.includes(query);
      })
      .sort((a, b) =>
        (b.rec.updatedAt || "").localeCompare(a.rec.updatedAt || ""),
      );
  }, [contacts, filter, search, startups]);

  const counts = useMemo(() => {
    const countMap = Object.fromEntries(
      CONTACT_STATUSES.map((status) => [status, 0]),
    ) as Record<ContactStatus, number>;
    for (const startup of startups) {
      const status = contacts[startup.id]?.status ?? DEFAULT_STATUS;
      countMap[status]++;
    }
    return countMap;
  }, [contacts, startups]);

  const error = healthQuery.error ?? startupsQuery.error;
  if (error) {
    return (
      <div className="mx-auto w-full max-w-7xl p-4 md:p-6">
        <ApiErrorDisplay
          error={error as unknown as ApiError}
          onRetry={() => {
            void healthQuery.refetch();
            void startupsQuery.refetch();
          }}
        />
      </div>
    );
  }

  if (healthQuery.isLoading || startupsQuery.isLoading) {
    return <ContactsSkeleton />;
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-5 p-4 md:p-6">
      <Card className="p-4 md:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Handshake className="h-4 w-4 text-primary" />
              <h1 className="text-base font-semibold text-foreground md:text-lg">
                Empresas em pipeline comercial
              </h1>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Controle de contato usando startups reais da API. Canais de
              contato ainda nao existem no backend.
            </p>
          </div>
          <Badge variant="outline" className="text-[11px]">
            {startups.length} startup(s) reais
          </Badge>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          {CONTACT_STATUSES.map((status) => (
            <button
              key={status}
              onClick={() => setFilter(status)}
              className={`rounded-md border px-3 py-2 text-left transition ${filter === status ? "border-primary/40 bg-primary/5" : "border-border hover:bg-muted/40"}`}
            >
              <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                {status}
              </p>
              <p className="mt-0.5 text-lg font-semibold tabular-nums text-foreground">
                {counts[status]}
              </p>
            </button>
          ))}
        </div>
      </Card>

      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar empresa..."
            className="h-9 sm:max-w-xs"
          />
          <Select
            value={filter}
            onValueChange={(v) => setFilter(v as ContactStatus | "Todas")}
          >
            <SelectTrigger className="h-9 w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {FILTERS.map((item) => (
                <SelectItem key={item} value={item}>
                  {item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Badge variant="outline" className="ml-auto text-[11px]">
            {rows.length} resultado(s)
          </Badge>
        </div>
      </Card>

      <Card className="overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] border-collapse text-sm">
            <thead className="bg-muted/50 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Empresa</th>
                <th className="px-3 py-2 font-medium">Classificacao</th>
                <th className="px-3 py-2 font-medium">Contato principal</th>
                <th className="px-3 py-2 font-medium">Canal</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Atualizado</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ startup, rec }) => {
                const founders = parseListField(startup.founders);
                return (
                  <tr
                    key={startup.id}
                    className="border-t border-border hover:bg-muted/30"
                  >
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2.5">
                        <Link
                          to="/startup/$id"
                          params={{ id: startup.id }}
                          aria-label={`Abrir perfil de ${startup.name}`}
                          className="rounded-md outline-none ring-primary/40 transition hover:opacity-85 focus-visible:ring-2"
                        >
                          <CompanyLogo
                            id={startup.id}
                            name={startup.name}
                            size="sm"
                          />
                        </Link>
                        <div className="min-w-0">
                          <div className="truncate font-medium text-foreground">
                            {startup.name}
                          </div>
                          <div className="truncate text-[11px] text-muted-foreground">
                            {unavailable(startup.sector)}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <Badge variant="outline" className="text-[10px]">
                        {startup.classification_label ?? "Nao classificada"}
                      </Badge>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="text-xs font-medium text-foreground">
                        {founders[0] ?? "Nao disponivel"}
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        Founder/contato nao validado
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex flex-col gap-0.5 text-[11px]">
                        <span className="inline-flex items-center gap-1 text-muted-foreground">
                          <Mail className="h-3 w-3" /> Nao disponivel
                        </span>
                        <span className="inline-flex items-center gap-1 text-muted-foreground">
                          <Phone className="h-3 w-3" /> Nao disponivel
                        </span>
                      </div>
                    </td>
                    <td className="w-[200px] px-3 py-2.5">
                      <Select
                        value={rec.status}
                        onValueChange={(v) =>
                          setContactStatus(startup.id, v as ContactStatus)
                        }
                      >
                        <SelectTrigger className="h-8 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {CONTACT_STATUSES.map((status) => (
                            <SelectItem
                              key={status}
                              value={status}
                              className="text-xs"
                            >
                              {status}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </td>
                    <td className="px-3 py-2.5 text-[11px] tabular-nums text-muted-foreground">
                      {rec.updatedAt ? formatDate(rec.updatedAt) : "--"}
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <Button
                        asChild
                        size="sm"
                        variant="ghost"
                        className="gap-1 text-xs"
                      >
                        <Link to="/startup/$id" params={{ id: startup.id }}>
                          Abrir <ArrowRight className="h-3 w-3" />
                        </Link>
                      </Button>
                    </td>
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    className="px-3 py-10 text-center text-xs text-muted-foreground"
                  >
                    Nenhuma empresa com esse filtro.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="p-4">
        <SectionTitle title="Legenda de status" />
        <div className="flex flex-wrap gap-2">
          {CONTACT_STATUSES.map((status) => (
            <ContactStatusBadge key={status} status={status} />
          ))}
        </div>
      </Card>
    </div>
  );
}

function ContactsSkeleton() {
  return (
    <div className="mx-auto w-full max-w-7xl p-4 md:p-6">
      <Card className="p-4">
        <div className="space-y-3">
          <Skeleton className="h-6 w-64" />
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {[1, 2, 3, 4, 5, 6].map((item) => (
              <Skeleton key={item} className="h-16" />
            ))}
          </div>
          <Skeleton className="h-64 w-full" />
        </div>
      </Card>
    </div>
  );
}
