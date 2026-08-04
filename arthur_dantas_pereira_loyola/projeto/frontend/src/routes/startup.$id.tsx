import { createFileRoute, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Cpu,
  ExternalLink,
  FileText,
  Mail,
  Phone,
  ShieldCheck,
  User,
} from "lucide-react";
import { ApiErrorDisplay } from "@/components/api-error-display";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
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
  MaturityBadge,
  ScoreBar,
  SectionTitle,
} from "@/components/ui-bits";
import type { ApiError } from "@/lib/api";
import {
  findLatestRunForStartup,
  formatDate,
  maturityLabel,
  parseListField,
  scoreFromConfidence,
  unavailable,
} from "@/lib/api-derived";
import {
  CONTACT_STATUSES,
  setContactStatus,
  useContact,
  type ContactStatus,
} from "@/lib/contacts-store";
import { useRun, useRuns } from "@/lib/hooks/use-runs";
import { useRunClaims, useRunSources } from "@/lib/hooks/use-sources";
import { useContacts, useStartup } from "@/lib/hooks/use-startups";
import { ContactDiscoveryDialog } from "@/components/contact-discovery-dialog";

export const Route = createFileRoute("/startup/$id")({
  head: ({ params }) => ({ meta: [{ title: `${params.id} - NVIDIA Toph` }] }),
  component: StartupPage,
});

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-card p-3">
      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">
        {value}
      </p>
      <ScoreBar value={value} className="mt-2" />
    </div>
  );
}

function StartupPage() {
  const { id } = Route.useParams();
  const startupQuery = useStartup(id);
  const runsQuery = useRuns();
  const startup = startupQuery.data;
  const latestRun = useMemo(
    () => findLatestRunForStartup(startup, runsQuery.data ?? []),
    [startup, runsQuery.data],
  );
  const runQuery = useRun(latestRun?.id ?? null);
  const sourcesQuery = useRunSources(latestRun?.id ?? null);
  const claimsQuery = useRunClaims(latestRun?.id ?? null);
  const contact = useContact(id);
  const [note, setNote] = useState(contact.note ?? "");

  useEffect(() => setNote(contact.note ?? ""), [id, contact.note]);

  const contactsQuery = useContacts(id);
  const companyContacts = contactsQuery.data;
  const [contactDialogOpen, setContactDialogOpen] = useState(false);
  const handleContactsComplete = useCallback(() => {
    void contactsQuery.refetch();
  }, [contactsQuery]);

  const error =
    startupQuery.error ??
    runsQuery.error ??
    runQuery.error ??
    sourcesQuery.error ??
    claimsQuery.error;
  if (error) {
    return (
      <div className="mx-auto w-full max-w-7xl p-4 md:p-6">
        <ApiErrorDisplay
          error={error as unknown as ApiError}
          onRetry={() => {
            void startupQuery.refetch();
            void runsQuery.refetch();
            void runQuery.refetch();
            void sourcesQuery.refetch();
            void claimsQuery.refetch();
          }}
        />
      </div>
    );
  }

  if (startupQuery.isLoading || runsQuery.isLoading || !startup) {
    return <StartupSkeleton />;
  }

  const maturity = maturityLabel(startup.classification_label);
  const confidenceScore = scoreFromConfidence(
    startup.classification_confidence,
  );
  const founders = parseListField(startup.founders);
  const customers = parseListField(startup.customers);
  const technologies = parseListField(startup.cited_technologies);
  const recommendations = runQuery.data?.recommendations ?? [];
  const claims = claimsQuery.data ?? [];
  const sources = sourcesQuery.data ?? [];
  const nvidiaFit = Math.min(100, recommendations.length * 25);
  const evidenceScore =
    claims.length > 0
      ? Math.round(
          (claims.reduce((sum, claim) => sum + claim.confidence, 0) /
            claims.length) *
            100,
        )
      : 0;

  return (
    <div className="mx-auto w-full max-w-7xl space-y-5 p-4 md:p-6">
      <div className="flex items-center justify-between gap-2">
        <Button asChild variant="ghost" size="sm" className="gap-1 text-xs">
          <Link to="/ranking">
            <ArrowLeft className="h-3.5 w-3.5" /> Ranking
          </Link>
        </Button>
        <Button asChild size="sm" className="gap-1.5">
          <Link to="/briefing">
            <FileText className="h-4 w-4" /> Gerar briefing
          </Link>
        </Button>
      </div>

      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-4">
            <CompanyLogo id={startup.id} name={startup.name} size="lg" domain={sources[0]?.domain} />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="truncate text-xl font-semibold text-foreground md:text-2xl">
                  {startup.name}
                </h1>
                {maturity ? (
                  <MaturityBadge value={maturity} />
                ) : (
                  <Badge variant="outline">Nao classificada</Badge>
                )}
                <ContactStatusBadge status={contact.status} />
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {unavailable(startup.sector)} - {unavailable(startup.product)}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Funding: {unavailable(startup.funding)} - Ultima atualizacao:{" "}
                {formatDate(startup.updated_at)}
              </p>
            </div>
          </div>
          <div className="rounded-md border border-primary/30 bg-primary/5 px-4 py-2 text-center">
            <p className="text-[10px] uppercase tracking-wider text-primary">
              Confianca
            </p>
            <p className="text-3xl font-bold tabular-nums text-primary">
              {confidenceScore}
            </p>
          </div>
        </div>
      </Card>

      <ContactDiscoveryDialog
        open={contactDialogOpen}
        onOpenChange={setContactDialogOpen}
        startupId={id}
        apiBase={import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}
        onComplete={handleContactsComplete}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <SectionTitle
            title="Contato da empresa"
            desc={companyContacts ? "Dados extraidos de fontes publicas." : "Clique em 'Buscar contatos' para descobrir."}
            right={
              <Button
                size="sm"
                variant="outline"
                className="gap-1.5 text-xs"
                onClick={() => setContactDialogOpen(true)}
              >
                Buscar contatos
              </Button>
            }
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <InfoBox
              icon={<User className="h-4 w-4" />}
              label="Contato principal"
              value={companyContacts?.primary_name ?? "Nao disponivel"}
              detail={companyContacts?.primary_role ?? "Cargo nao encontrado"}
            />
            <InfoBox
              icon={<Mail className="h-4 w-4" />}
              label="E-mail"
              value={companyContacts?.emails?.[0]?.value ?? "Nao disponivel"}
              detail={
                companyContacts?.emails?.length
                  ? `${companyContacts.emails.length} email(s) encontrados`
                  : "Nenhum email encontrado"
              }
            />
            <InfoBox
              icon={<Phone className="h-4 w-4" />}
              label="Telefone"
              value={companyContacts?.phones?.[0]?.value ?? "Nao disponivel"}
              detail={
                companyContacts?.phones?.length
                  ? `${companyContacts.phones.length} telefone(s) encontrados`
                  : "Nenhum telefone encontrado"
              }
            />
            <InfoBox
              icon={<ExternalLink className="h-4 w-4" />}
              label="LinkedIn"
              value={
                companyContacts?.linkedin_urls?.[0]?.value
                  ? "Ver perfil"
                  : "Nao disponivel"
              }
              detail={
                companyContacts?.linkedin_urls?.[0]?.value ?? "Nenhum LinkedIn encontrado"
              }
            />
          </div>
        </Card>

        <Card className="p-5">
          <SectionTitle
            title="Status do contato"
            desc="Estado local salvo no navegador."
          />
          <Select
            value={contact.status}
            onValueChange={(v) =>
              setContactStatus(startup.id, v as ContactStatus, note)
            }
          >
            <SelectTrigger className="h-9 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CONTACT_STATUSES.map((cs) => (
                <SelectItem key={cs} value={cs} className="text-sm">
                  {cs}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="mt-3 space-y-1">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Notas internas
            </p>
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              onBlur={() => setContactStatus(startup.id, contact.status, note)}
              placeholder="Ultima conversa, proximos passos, blockers..."
              className="min-h-[80px] text-xs"
            />
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Ultima atualizacao:{" "}
            {contact.updatedAt ? formatDate(contact.updatedAt) : "--"}
          </p>
        </Card>
      </div>

      <Card className="p-5">
        <SectionTitle title="Resumo executivo" />
        <p className="text-sm leading-relaxed text-foreground">
          {startup.description ??
            startup.ai_usage_summary ??
            "Descricao ainda nao disponivel na API."}
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <InfoList title="Founders" items={founders} />
          <InfoList title="Clientes" items={customers} />
          <InfoList title="Tecnologias citadas" items={technologies} />
          <InfoList
            title="Run associado"
            items={
              latestRun
                ? [`#${latestRun.id} - ${latestRun.query}`]
                : ["Nenhum run associado ainda"]
            }
          />
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="Classificacao" value={confidenceScore} />
        <StatCard label="Evidence" value={evidenceScore} />
        <StatCard label="NVIDIA fit" value={nvidiaFit} />
        <StatCard
          label="Recomendacoes"
          value={Math.min(100, recommendations.length * 20)}
        />
      </div>

      <Card className="p-5">
        <SectionTitle
          title="Evidencias publicas"
          desc="Claims e fontes persistidos pelo run mais recente associado."
        />
        {claims.length === 0 ? (
          <EmptyText text="Nenhuma evidencia associada a esta startup ainda." />
        ) : (
          <div className="space-y-2">
            {claims.map((claim, index) => (
              <div
                key={claim.id}
                className="rounded-md border border-border p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Badge variant="outline" className="text-[10px]">
                    E{index + 1} - {claim.claim_type}
                  </Badge>
                  <span className="text-[11px] text-muted-foreground">
                    conf. {scoreFromConfidence(claim.confidence)}
                  </span>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-foreground">
                  {claim.text}
                </p>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="p-5">
        <SectionTitle
          title="Fontes do run"
          desc="URLs reais usadas pelo pipeline."
        />
        {sources.length === 0 ? (
          <EmptyText text="Nenhuma fonte associada a esta startup ainda." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] border-collapse text-sm">
              <thead className="bg-muted/40 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">Fonte</th>
                  <th className="px-3 py-2">Tipo</th>
                  <th className="px-3 py-2">Claims</th>
                  <th className="px-3 py-2">Coleta</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((source) => (
                  <tr key={source.id} className="border-t border-border">
                    <td className="max-w-md px-3 py-2">
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noreferrer"
                        className="truncate text-xs text-primary hover:underline"
                      >
                        {source.title || source.url}
                      </a>
                      <p className="text-[11px] text-muted-foreground">
                        {source.domain}
                      </p>
                    </td>
                    <td className="px-3 py-2 text-xs">{source.source_type}</td>
                    <td className="px-3 py-2 text-xs tabular-nums">
                      {source.claim_count}
                    </td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {formatDate(source.retrieved_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card className="p-5">
        <SectionTitle
          title="Recomendacoes NVIDIA"
          desc="Vem de GET /runs/{id}; sem fallback ficticio."
        />
        {recommendations.length === 0 ? (
          <EmptyText text="Nenhuma recomendacao real associada a este run ainda." />
        ) : (
          <div className="space-y-3">
            {recommendations.map((rec) => (
              <div key={rec.id} className="rounded-md border border-border p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
                      <Cpu className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-foreground">
                        {rec.technology}
                      </p>
                      <p className="text-[11px] text-muted-foreground">
                        {rec.suggested_next_action}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <Badge variant="outline" className="text-[10px]">
                      Prioridade {rec.priority}
                    </Badge>
                    <Badge variant="outline" className="text-[10px]">
                      Complexidade {rec.implementation_complexity}
                    </Badge>
                  </div>
                </div>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <p className="text-xs text-foreground">
                    <span className="font-medium">Tecnico:</span>{" "}
                    {rec.technical_justification}
                  </p>
                  <p className="text-xs text-foreground">
                    <span className="font-medium">Negocio:</span>{" "}
                    {rec.business_justification}
                  </p>
                </div>
                <div className="mt-3 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <ShieldCheck className="h-3 w-3 text-primary" /> Evidencias:{" "}
                  {rec.startup_evidence_ids || "--"}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function StartupSkeleton() {
  return (
    <div className="mx-auto w-full max-w-7xl p-4 md:p-6">
      <Card className="p-5">
        <div className="space-y-3">
          <div className="flex items-center gap-4">
            <Skeleton className="h-14 w-14 rounded-md" />
            <div className="space-y-2">
              <Skeleton className="h-6 w-56" />
              <Skeleton className="h-4 w-72" />
            </div>
          </div>
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </Card>
    </div>
  );
}

function InfoBox({
  icon,
  label,
  value,
  detail,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-md border border-border p-3">
      <div className="flex items-center gap-2 text-muted-foreground">
        {icon}
        <p className="text-[10px] uppercase tracking-wider">{label}</p>
      </div>
      <p className="mt-1 truncate text-sm font-medium text-foreground">
        {value}
      </p>
      <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
        {detail}
      </p>
    </div>
  );
}

function InfoList({ title, items }: { title: string; items: string[] }) {
  const visible = items.length > 0 ? items : ["Nao disponivel"];
  return (
    <div className="rounded-md border border-border p-3">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {title}
      </p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {visible.map((item) => (
          <Badge key={item} variant="outline" className="text-[10px]">
            {item}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function EmptyText({ text }: { text: string }) {
  return (
    <div className="rounded-md border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
      {text}
    </div>
  );
}
