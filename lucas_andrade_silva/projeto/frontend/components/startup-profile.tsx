"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Building2,
  CalendarClock,
  CheckCircle2,
  ExternalLink,
  FileCheck2,
  Github,
  Globe2,
  Linkedin,
  LoaderCircle,
  Mail,
  MapPin,
  Phone,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Users
} from "lucide-react";
import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { ApiErrorState, InsufficientData } from "@/components/feedback";
import { NvidiaRecommendations } from "@/components/nvidia-recommendations";
import { ReviewDecisionDialog } from "@/components/review-decision-dialog";
import { StartupLogo } from "@/components/startup-logo";
import { TechnologyIntelligence } from "@/components/technology-intelligence";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  getJob,
  getStartup,
  startCompanyRegistrationEnrichment,
  updateStartup
} from "@/lib/api";
import {
  hasCompanyRegistrationData,
  partnerName,
  partnerRole,
  resolveCompanyData,
  usefulText
} from "@/lib/company-data";
import {
  displayStartupAiLabel,
  statusMeta
} from "@/lib/status";
import { translateIfEnglish } from "@/lib/translate";
import type { Startup } from "@/lib/types";
import { cn, formatDate, getDomain } from "@/lib/utils";

export function StartupProfile({ startupId }: { startupId: string }) {
  const [jobId, setJobId] = useState<string>();
  const automaticRequestStarted = useRef(false);
  const query = useQuery({
    queryKey: ["startup", startupId],
    queryFn: ({ signal }) => getStartup(startupId, signal),
    refetchInterval: (activeQuery) => {
      const startup = activeQuery.state.data;
      return jobId && startup && !hasCompanyRegistrationData(startup)
        ? 2_000
        : false;
    },
    refetchIntervalInBackground: true
  });
  const enrichmentMutation = useMutation({
    mutationFn: () => startCompanyRegistrationEnrichment(startupId),
    onSuccess: (job) => setJobId(job.job_id)
  });
  const jobQuery = useQuery({
    queryKey: ["startup-enrichment-job", jobId],
    queryFn: ({ signal }) => getJob(jobId!, signal),
    enabled: Boolean(jobId),
    retry: 2,
    refetchInterval: (activeQuery) => {
      const status = activeQuery.state.data?.status;
      return status === "completed" || status === "failed" ? false : 1500;
    },
    refetchIntervalInBackground: true
  });
  const hasRegistrationData = query.data
    ? hasCompanyRegistrationData(query.data)
    : false;

  useEffect(() => {
    if (
      query.data &&
      !hasRegistrationData &&
      !automaticRequestStarted.current
    ) {
      automaticRequestStarted.current = true;
      enrichmentMutation.mutate();
    }
  }, [query.data, hasRegistrationData, enrichmentMutation]);

  useEffect(() => {
    if (hasRegistrationData && jobId) {
      setJobId(undefined);
    }
  }, [hasRegistrationData, jobId]);

  useEffect(() => {
    const status = jobQuery.data?.status;
    if (status === "completed") {
      void query.refetch();
      setJobId(undefined);
    } else if (status === "failed") {
      setJobId(undefined);
    }
  }, [jobQuery.data?.status, query]);

  if (query.isLoading) return <InitialValidationScreen />;

  if (query.isError || !query.data) {
    return (
      <main className="mx-auto w-full max-w-[1500px] px-4 py-6 lg:px-8">
        <BackLink />
        <Card className="mt-5">
          <ApiErrorState
            message={
              query.error instanceof Error
                ? query.error.message
                : "Não foi possível carregar a startup."
            }
            onRetry={() => query.refetch()}
          />
        </Card>
      </main>
    );
  }

  return (
    <ProfileContent
      startup={query.data}
      enriching={
        enrichmentMutation.isPending ||
        Boolean(
          jobId &&
            !hasRegistrationData &&
            !jobQuery.isError &&
            jobQuery.data?.status !== "completed" &&
            jobQuery.data?.status !== "failed"
        )
      }
      enrichmentError={
        enrichmentMutation.error ||
        jobQuery.error ||
        (jobQuery.data?.status === "failed"
          ? new Error(jobQuery.data.error || "Falha no enriquecimento.")
          : undefined)
      }
      onRefresh={() => {
        automaticRequestStarted.current = true;
        enrichmentMutation.mutate();
      }}
    />
  );
}

function ProfileContent({
  startup,
  enriching,
  enrichmentError,
  onRefresh
}: {
  startup: Startup;
  enriching: boolean;
  enrichmentError?: Error | null;
  onRefresh: () => void;
}) {
  const queryClient = useQueryClient();
  const [reviewDialogOpen, setReviewDialogOpen] = useState(false);
  const status = statusMeta(startup.validation_status);
  const StatusIcon = status.Icon;
  const url = startup.validated_url || startup.website;
  const techCoverage = technologyCoverage(startup.technology_intelligence);
  const techConfidence = techCoverage?.score ?? normalizeScore(startup.tech_confidence_score);
  const companyData = resolveCompanyData(startup);
  const headquarters =
    companyData.localizacao || cleanValue(startup.location);
  const openingDate =
    formatBusinessDate(companyData.abertura) ||
    cleanValue(
      startup.founding_year ? String(startup.founding_year) : undefined
    );
  const identityCompletion = identityFieldCompletion({
    startup,
    companyData,
    domain: url ? getDomain(url) : undefined,
    headquarters,
    openingDate,
    validationStatus: startup.validation_status,
    aiClassification: startup.ai_dependency_level
  });
  const identityConfidence = identityCompletion.score;
  const reviewMutation = useMutation({
    mutationFn: (decision: "APPROVED" | "DISCARDED") =>
      updateStartup(String(startup.id || startup.candidate_id || ""), {
        validation_status: decision,
        ...(decision === "DISCARDED" ? { is_active: false } : {})
      }),
    onSuccess: () => {
      setReviewDialogOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["startup"] });
      void queryClient.invalidateQueries({ queryKey: ["startups"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    }
  });

  return (
    <main className="mx-auto w-full min-w-0 max-w-[1500px] px-4 py-6 lg:px-8">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Link href="/startups" className="hover:text-foreground">
            Startups
          </Link>
          <span>/</span>
          <span className="text-foreground">
            {startup.company_name || "Dados insuficientes"}
          </span>
        </div>
        <Button variant="outline" size="sm" disabled={enriching} onClick={onRefresh}>
          <RefreshCw className={cn("mr-2 size-3.5", enriching && "animate-spin")} />
          {enriching ? "Enriquecendo dados..." : "Atualizar dados"}
        </Button>
      </div>

      {enrichmentError && (
        <Card className="mt-4 border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
          Não foi possível atualizar os dados cadastrais:{" "}
          {enrichmentError.message}
        </Card>
      )}

      {enriching && (
        <Card className="mt-4 border-primary/20 bg-primary/5 p-3 text-xs text-primary">
          <div className="flex items-center gap-2">
            <LoaderCircle className="size-3.5 animate-spin" />
            Validando dados em segundo plano. A visão detalhada permanece disponível.
          </div>
        </Card>
      )}

      <section className="mt-5 flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          <StartupLogo
            className="size-20 rounded-xl bg-primary/10 shadow-glow"
            imageClassName="p-2"
            website={url}
            name={startup.company_name}
          />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-3xl font-semibold tracking-tight">
                {startup.company_name || "Nome não informado"}
              </h1>
              <Badge className={status.className}>
                <StatusIcon className="mr-1 size-3.5" />
                {status.label}
              </Badge>
              {startup.validation_status === "REVIEW" && (
                <Button
                  aria-label="Aprovar startup em revisão"
                  disabled={reviewMutation.isPending}
                  size="icon"
                  title="Decidir revisao"
                  variant="outline"
                  onClick={() => setReviewDialogOpen(true)}
                >
                  <CheckCircle2 className="size-4" />
                </Button>
              )}
              {startup.ai_dependency_level && (
                <Badge className="border-primary/30 bg-primary/5 text-primary">
                  <Sparkles className="mr-1 size-3.5" />
                  {displayStartupAiLabel(startup)}
                </Badge>
              )}
            </div>
            {url ? (
              <a
                className="mt-2 inline-flex max-w-full items-center gap-2 text-sm text-muted-foreground hover:text-primary"
                href={externalUrl(url)}
                rel="noreferrer"
                target="_blank"
              >
                <Globe2 className="size-4 shrink-0" />
                <span className="truncate">{getDomain(url)}</span>
                <ExternalLink className="size-3.5 shrink-0" />
              </a>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">
                Domínio: dados insuficientes
              </p>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              <DataTag value={cleanValue(startup.ai_technology_focus)} />
              <DataTag value={cleanValue(startup.target_market)} />
              {!cleanValue(startup.ai_technology_focus) &&
                !cleanValue(startup.target_market) && (
                  <Badge className="text-muted-foreground">Dados insuficientes</Badge>
                )}
            </div>
          </div>
        </div>
      </section>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <MetricCard
          label="Confiança de identidade"
          value={scoreLabel(identityConfidence)}
          detail={`${identityCompletion.completed} de ${identityCompletion.total} campos preenchidos`}
          progress={identityConfidence}
          icon={ShieldCheck}
        />
        <ConfidenceMetricCard
          identity={identityConfidence}
          technology={techConfidence}
        />
        <MetricCard
          label="Última atualização"
          value={startup.updated_at ? formatDate(startup.updated_at) : "Dados insuficientes"}
          detail="Conforme registro da API"
          icon={CalendarClock}
        />
      </div>

      <div className="mt-3 grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 gap-3 lg:columns-2">
          <SectionCard title="1. Visão geral da startup">
            <KeyValue label="Nome" value={startup.company_name} />
            <KeyValue label="Domínio" value={url ? getDomain(url) : undefined} />
            <KeyValue label="Sede" value={headquarters} />
            <KeyValue label="Fundação" value={openingDate} />
            <KeyValue label="CNPJ" value={companyData.cnpj} />
            <KeyValue label="Status" value={status.label} />
            <KeyValue
              label="Classificação de IA"
              value={displayStartupAiLabel(startup)}
            />
          </SectionCard>

          <SectionCard title="2. Descrição da empresa">
            {startup.company_description || startup.description ? (
              <p className="text-sm leading-6 text-muted-foreground">
                {displayDescription(startup.company_description || startup.description)}
              </p>
            ) : (
              <MissingText />
            )}
            {cleanValue(startup.key_milestones) && (
              <div className="mt-5 border-t border-border pt-4">
                <p className="text-xs font-medium text-foreground">Marcos relevantes</p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {translateIfEnglish(startup.key_milestones)}
                </p>
              </div>
            )}
          </SectionCard>

          <SectionCard title="3. Dados cadastrais e contato">
            <KeyValue
              label="Razão social"
              value={companyData.razaoSocial}
            />
            <KeyValue
              label="Nome fantasia"
              value={companyData.nomeFantasia}
            />
            <KeyValue label="CNPJ" value={companyData.cnpj} />
            <KeyValue
              label="Situação cadastral"
              value={companyData.situacao}
            />
            <KeyValue label="Data de abertura" value={openingDate} />
            <KeyValue label="Município / UF" value={headquarters} />
            <KeyValue label="CNAE principal" value={companyData.cnae} />
            <KeyValue
              label="Natureza jurídica"
              value={companyData.naturezaJuridica}
            />
            <KeyValue label="Porte" value={companyData.porte} />
            <KeyValue
              label="Capital social"
              value={companyData.capitalSocial}
            />
            <ContactValue
              icon={Phone}
              label="Telefone"
              value={companyData.telefone}
            />
            <ContactValue
              icon={Mail}
              label="E-mail"
              value={companyData.email}
            />
            <ContactValue
              icon={MapPin}
              label="Endereço"
              value={companyData.endereco}
            />
          </SectionCard>

          <SectionCard
            className="lg:col-span-2"
            title={`4. Quadro societário${
              companyData.socios.length
                ? ` (${companyData.socios.length})`
                : ""
            }`}
          >
            {companyData.socios.length ? (
              <div className="max-h-96 overflow-y-auto pr-1">
                {companyData.socios.map((partner, index) => (
                  <PartnerRow
                    key={`${partnerName(partner) || "socio"}-${index}`}
                    partner={partner}
                  />
                ))}
              </div>
            ) : (
              <MissingText />
            )}
          </SectionCard>

          <SectionCard title="5. Provável stack tecnológica">
            <TechnologyIntelligence
              startupId={String(startup.id || startup.candidate_id || "")}
              initialReport={startup.technology_intelligence}
            />
          </SectionCard>
        </div>

        <aside className="space-y-3">
          <SourcesCard startup={startup} />
          <NvidiaRecommendations
            startupId={String(startup.id || startup.candidate_id || "")}
            companyName={startup.company_name || "esta startup"}
            initialResult={startup.nvidia_recommendation}
          />
        </aside>
      </div>
      <div id="nvidia-recommendations" />
      {reviewDialogOpen && (
        <ReviewDecisionDialog
          companyName={startup.company_name}
          loading={reviewMutation.isPending}
          onApprove={() => reviewMutation.mutate("APPROVED")}
          onDiscard={() => reviewMutation.mutate("DISCARDED")}
          onClose={() => setReviewDialogOpen(false)}
        />
      )}
    </main>
  );
}

function InitialValidationScreen() {
  return (
    <main className="grid min-h-[calc(100vh-80px)] place-items-center p-4">
      <Card className="w-full max-w-md p-6 text-center">
        <LoaderCircle className="mx-auto size-8 animate-spin text-primary" />
        <h2 className="mt-4 text-lg font-semibold">Validando dados da startup</h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Estamos conferindo dados cadastrais, fontes e evidências antes de exibir a visão detalhada.
        </p>
        <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
          <div className="h-full w-2/3 rounded-full bg-primary" />
        </div>
      </Card>
    </main>
  );
}

function MetricCard({
  label,
  value,
  detail,
  progress,
  icon: Icon
}: {
  label: string;
  value: string;
  detail: string;
  progress?: number;
  icon: LucideIcon;
}) {
  return (
    <Card className="flex min-h-32 items-center justify-between gap-4 overflow-hidden p-4">
      <p className="pr-10 text-xs text-muted-foreground">{label}</p>
      <p className={cn("mt-2 pr-9 font-semibold", progress !== undefined ? "text-2xl text-primary" : "text-base")}>
        {value}
      </p>
      <div className="absolute right-4 top-4 grid size-9 place-items-center rounded-full bg-primary/10 text-primary">
        <Icon className="size-[18px]" />
      </div>
      {progress !== undefined && (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
          <div className="h-full rounded-full bg-primary" style={{ width: `${progress}%` }} />
        </div>
      )}
      <p className="mt-3 text-[11px] text-muted-foreground">{detail}</p>
    </Card>
  );
}

function ConfidenceMetricCard({
  technology
}: {
  identity?: number;
  technology?: number;
}) {
  const score = technology;

  return (
    <Card className="relative min-h-32 overflow-hidden p-4">
      <p className="pr-20 text-xs text-muted-foreground">Detalhamento de confiança</p>
      <div className="shrink-0">
        <CircularScore value={score} />
      </div>
    </Card>
  );
}

function CircularScore({ value }: { value?: number }) {
  const normalized = Math.max(0, Math.min(100, value ?? 0));
  const radius = 17;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (normalized / 100) * circumference;
  return (
    <div className="relative grid size-14 place-items-center rounded-full bg-primary/5 text-primary">
      <svg className="size-14 -rotate-90" viewBox="0 0 44 44" aria-hidden="true">
        <circle
          className="stroke-white/[0.08]"
          cx="22"
          cy="22"
          fill="none"
          r={radius}
          strokeWidth="4"
        />
        <circle
          className="stroke-primary"
          cx="22"
          cy="22"
          fill="none"
          r={radius}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          strokeWidth="4"
        />
      </svg>
      <span className="absolute text-[11px] font-semibold">
        {value === undefined ? "--" : `${normalized}%`}
      </span>
    </div>
  );
}

function SectionCard({
  title,
  children,
  className
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("mb-3 min-w-0 break-inside-avoid p-4", className)}>
      <h2 className="mb-4 text-sm font-semibold">{title}</h2>
      {children}
    </Card>
  );
}

function ContactValue({
  icon: Icon,
  label,
  value
}: {
  icon: LucideIcon;
  label: string;
  value?: string;
}) {
  return (
    <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3 border-b border-border/60 py-2 text-xs last:border-0">
      <span className="flex items-center gap-1.5 text-muted-foreground">
        <Icon className="size-3.5 shrink-0" />
        {label}
      </span>
      <span className={cn("break-words", !value && "text-muted-foreground")}>
        {value || "Dados insuficientes"}
      </span>
    </div>
  );
}

function PartnerRow({
  partner
}: {
  partner: NonNullable<Startup["socios"]>[number];
}) {
  const name = partnerName(partner);
  const role = partnerRole(partner);
  return (
    <div className="flex items-start gap-3 border-b border-border/60 py-3 last:border-0">
      <div className="grid size-8 shrink-0 place-items-center rounded-full bg-primary/10 text-primary">
        <Users className="size-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="break-words text-xs font-medium">
          {name || "Sócio não informado"}
        </p>
        <p className="mt-1 text-[11px] text-muted-foreground">
          {role || "Qualificação não informada"}
        </p>
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-muted-foreground">
          {usefulText(partner.data_entrada) && (
            <span>Entrada: {formatBusinessDate(partner.data_entrada)}</span>
          )}
          {usefulText(partner.cpf_cnpj_mascarado) && (
            <span>Documento: {partner.cpf_cnpj_mascarado}</span>
          )}
          {usefulText(partner.representante_legal) && (
            <span>Representante: {partner.representante_legal}</span>
          )}
        </div>
      </div>
    </div>
  );
}

function KeyValue({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3 border-b border-border/60 py-2 text-xs last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("break-words", !value && "text-muted-foreground")}>
        {value || "Dados insuficientes"}
      </span>
    </div>
  );
}

function SourcesCard({ startup }: { startup: Startup }) {
  const sources = [
    {
      label: "Site validado",
      url: startup.validated_url,
      icon: Globe2,
      validated: true
    },
    {
      label: "Site informado",
      url: startup.website,
      icon: Globe2,
      validated: false
    },
    {
      label: "Fonte principal",
      url: startup.source_url,
      icon: FileCheck2,
      validated: false
    },
    {
      label: "LinkedIn",
      url: startup.linkedin_url,
      icon: Linkedin,
      validated: false
    },
    {
      label: "Crunchbase",
      url: startup.crunchbase_url,
      icon: Building2,
      validated: false
    },
    {
      label: "GitHub",
      url: startup.github_org,
      icon: Github,
      validated: false
    }
  ].filter((source) => Boolean(source.url));

  return (
    <Card className="p-4">
      <h2 className="text-sm font-semibold">Fontes e evidências</h2>
      {sources.length === 0 ? (
        <InsufficientData message="Nenhuma fonte foi informada pela API." />
      ) : (
        <div className="mt-3">
          {sources.map(({ label, url, icon: Icon, validated }) => (
            <a
              className="flex items-start gap-3 border-b border-border/60 py-3 last:border-0 hover:text-primary"
              href={sourceUrl(label, String(url))}
              key={`${label}-${url}`}
              rel="noreferrer"
              target="_blank"
            >
              <Icon className="mt-0.5 size-4 shrink-0 text-primary" />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium">{label}</p>
                <p className="mt-1 truncate text-[10px] text-muted-foreground">
                  {String(url)}
                </p>
              </div>
              <Badge
                className={cn(
                  "shrink-0",
                  validated
                    ? "border-primary/20 bg-primary/10 text-primary"
                    : "text-muted-foreground"
                )}
              >
                {validated ? "Validada" : "Disponível"}
              </Badge>
            </a>
          ))}
        </div>
      )}
    </Card>
  );
}

function DataTag({ value }: { value?: string }) {
  return value ? (
    <Badge className="bg-white/[0.025] text-muted-foreground">{value}</Badge>
  ) : null;
}

function MissingText() {
  return <p className="text-sm text-muted-foreground">Dados insuficientes.</p>;
}

function BackLink() {
  return (
    <Button variant="ghost" size="sm" asChild>
      <Link href="/startups">
        <ArrowLeft className="mr-2 size-4" />
        Voltar para startups
      </Link>
    </Button>
  );
}

function cleanValue(value?: string | null) {
  if (!value) return undefined;
  const normalized = value.trim().toUpperCase();
  if (
    [
      "UNKNOWN",
      "NONE",
      "NOT SPECIFIED",
      "N/A",
      "NULL",
      "DADOS INSUFICIENTES",
      "NAO INFORMADO",
      "NÃO INFORMADO"
    ].includes(normalized)
  ) {
    return undefined;
  }
  return value.trim();
}

function displayDescription(value?: string | null) {
  return translateIfEnglish(
    String(value || "")
    .replace(/Descricao original em ingles preservada como evidencia:\s*/gi, "")
    .replace(/Descrição original em inglês preservada como evidência:\s*/gi, "")
    .trim()
  );
}

function technologyCoverage(report?: Startup["technology_intelligence"]) {
  if (!report) return undefined;
  const requirements = [
    { label: "backend", found: report.infraestrutura_backend.length > 0 },
    { label: "frontend/mobile", found: report.frontend_mobile.length > 0 },
    { label: "IA operacional", found: report.ia_operacional_interna.length > 0 },
    { label: "IA no produto", found: report.ia_produto_core.length > 0 }
  ];
  const found = requirements.filter((item) => item.found).length;
  return {
    score: Math.round((found / requirements.length) * 100),
    detail: `${found} de ${requirements.length} frentes tecnológicas encontradas`
  };
}

function identityFieldCompletion({
  startup,
  companyData,
  domain,
  headquarters,
  openingDate,
  validationStatus,
  aiClassification
}: {
  startup: Startup;
  companyData: ReturnType<typeof resolveCompanyData>;
  domain?: string;
  headquarters?: string;
  openingDate?: string;
  validationStatus?: string | null;
  aiClassification?: string | null;
}) {
  const fields = [
    startup.company_name,
    domain,
    headquarters,
    openingDate,
    companyData.cnpj,
    validationStatus,
    aiClassification,
    companyData.razaoSocial,
    companyData.nomeFantasia,
    companyData.cnpj,
    companyData.situacao,
    openingDate,
    headquarters,
    companyData.cnae,
    companyData.naturezaJuridica,
    companyData.porte,
    companyData.capitalSocial,
    companyData.telefone,
    companyData.email,
    companyData.endereco
  ];
  const completed = fields.filter((value) => Boolean(cleanValue(value))).length;
  return {
    completed,
    total: fields.length,
    score: Math.round((completed / fields.length) * 100)
  };
}

function formatBusinessDate(value?: string | null) {
  const text = usefulText(value);
  if (!text) return undefined;
  const isoMatch = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (isoMatch) {
    return `${isoMatch[3]}/${isoMatch[2]}/${isoMatch[1]}`;
  }
  return text;
}

function normalizeScore(value?: number | null) {
  if (typeof value !== "number" || Number.isNaN(value)) return undefined;
  const normalized = value <= 1 ? value * 100 : value;
  return Math.round(Math.max(0, Math.min(100, normalized)));
}

function scoreLabel(value?: number) {
  return value === undefined ? "Dados insuficientes" : `${value}%`;
}

function scoreDetail(value?: number) {
  if (value === undefined) return "Score não informado";
  if (value >= 90) return "Excelente";
  if (value >= 75) return "Alta";
  if (value >= 50) return "Moderada";
  return "Baixa";
}

function externalUrl(value: string) {
  return value.startsWith("http") ? value : `https://${value}`;
}

function sourceUrl(label: string, value: string) {
  if (label === "GitHub" && !value.startsWith("http")) {
    return `https://github.com/${value.replace(/^@/, "")}`;
  }
  return externalUrl(value);
}
