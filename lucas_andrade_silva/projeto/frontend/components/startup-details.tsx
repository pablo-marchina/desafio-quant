"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ExternalLink,
  Github,
  Globe2,
  LoaderCircle,
  MapPin,
  Phone,
  Target,
  Users,
  ArrowRight,
  CheckCircle2,
  X
} from "lucide-react";
import Link from "next/link";

import { ApiErrorState } from "@/components/feedback";
import { useNavigationLoading } from "@/components/navigation-loading";
import { ReviewDecisionDialog } from "@/components/review-decision-dialog";
import { StartupLogo } from "@/components/startup-logo";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getStartup, updateStartup } from "@/lib/api";
import {
  partnerName,
  partnerRole,
  resolveCompanyData
} from "@/lib/company-data";
import { displayStartupAiLabel, statusMeta, toStringList } from "@/lib/status";
import { translateIfEnglish } from "@/lib/translate";
import type { Startup } from "@/lib/types";
import { cn, getDomain } from "@/lib/utils";
import { useState } from "react";

type Props = {
  startup: Startup;
  onClose: () => void;
};

export function StartupDetails({ startup, onClose }: Props) {
  const queryClient = useQueryClient();
  const { startLoading } = useNavigationLoading();
  const [reviewDialogOpen, setReviewDialogOpen] = useState(false);
  const id = String(startup.id || startup.candidate_id || "");
  const detailQuery = useQuery({
    queryKey: ["startup", id],
    queryFn: ({ signal }) => getStartup(id, signal),
    enabled: Boolean(id)
  });
  const item = detailQuery.data || startup;
  const meta = statusMeta(item?.validation_status);
  const techStack = toStringList(item?.tech_stack);
  const url = item?.validated_url || item?.website;
  const companyData = item ? resolveCompanyData(item) : undefined;
  const reviewMutation = useMutation({
    mutationFn: (decision: "APPROVED" | "DISCARDED") =>
      updateStartup(id, {
        validation_status: decision,
        ...(decision === "DISCARDED" ? { is_active: false } : {})
      }),
    onSuccess: () => {
      setReviewDialogOpen(false);
      void detailQuery.refetch();
      void queryClient.invalidateQueries({ queryKey: ["startups"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    }
  });

  function approveReview() {
    setReviewDialogOpen(true);
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-[2px]">
      <button className="flex-1 cursor-default" aria-label="Fechar detalhes" onClick={onClose} />
      <aside className="h-full w-full max-w-[420px] overflow-y-auto border-l border-border bg-[#0b1118] shadow-2xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-[#0b1118]/95 px-5 py-4 backdrop-blur">
          <p className="text-xs font-medium uppercase tracking-wider text-primary">
            Visão geral
          </p>
          <Button aria-label="Fechar" size="icon" variant="ghost" onClick={onClose}>
            <X className="size-4" />
          </Button>
        </div>
        {detailQuery.isError && !item ? (
          <ApiErrorState
            message={
              detailQuery.error instanceof Error
                ? detailQuery.error.message
                : "Falha ao consultar a startup."
            }
            onRetry={() => detailQuery.refetch()}
          />
        ) : !item ? (
          <DetailLoading />
        ) : (
          <div className="p-5">
            <div className="flex items-start gap-4">
              <StartupLogo
                className="size-14 rounded-lg"
                website={url}
                name={item.company_name}
              />
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="truncate text-xl font-semibold">
                    {item.company_name || "Nome não informado"}
                  </h2>
                  <Badge className={meta.className}>{meta.label}</Badge>
                  {item.validation_status === "REVIEW" && (
                    <Button
                      aria-label="Aprovar startup em revisão"
                      disabled={reviewMutation.isPending}
                      size="icon"
                      title="Decidir revisao"
                      variant="outline"
                      onClick={approveReview}
                    >
                      <CheckCircle2 className="size-4" />
                    </Button>
                  )}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{getDomain(url)}</p>
              </div>
            </div>

            <Section title="URL validada">
              {url ? (
                <a
                  className="flex items-center gap-2 rounded-md border border-border bg-white/[0.02] p-3 text-sm hover:border-primary/30"
                  href={url.startsWith("http") ? url : `https://${url}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <Globe2 className="size-4 text-primary" />
                  <span className="truncate">{url}</span>
                  <ExternalLink className="ml-auto size-4 text-muted-foreground" />
                </a>
              ) : (
                <Missing />
              )}
            </Section>

            <Section title="Classificação">
              <InfoRow
                label="Dependência de IA"
                value={displayStartupAiLabel(item)}
              />
              <InfoRow label="Foco tecnológico" value={item.ai_technology_focus} icon={Target} />
            </Section>

            <Section title="Stack tecnológica detectada">
              {techStack.length ? (
                <div className="flex flex-wrap gap-2">
                  {techStack.map((tech) => (
                    <Badge className="bg-white/[0.025] text-foreground" key={tech}>
                      {tech}
                    </Badge>
                  ))}
                </div>
              ) : (
                <Missing />
              )}
            </Section>

            <Section title="Informações gerais">
              <InfoRow
                label="Localização"
                value={companyData?.localizacao || item.location}
                icon={MapPin}
              />
              <InfoRow
                label="Fundação"
                value={
                  companyData?.abertura ||
                  (item.founding_year
                    ? String(item.founding_year)
                    : undefined)
                }
              />
              <InfoRow label="Mercado-alvo" value={item.target_market} />
              <InfoRow label="CNPJ" value={companyData?.cnpj} />
              <InfoRow label="GitHub" value={item.github_org} icon={Github} />
            </Section>

            <Section title="Dados cadastrais">
              <InfoRow
                label="Razão social"
                value={companyData?.razaoSocial}
              />
              <InfoRow
                label="Município / UF"
                value={companyData?.localizacao}
                icon={MapPin}
              />
              <InfoRow label="CNAE" value={companyData?.cnae} />
              <InfoRow
                label="Telefone"
                value={companyData?.telefone}
                icon={Phone}
              />
              <InfoRow
                label="Abertura"
                value={companyData?.abertura}
              />
              <InfoRow
                label="Endereço"
                value={companyData?.endereco}
                icon={MapPin}
              />
            </Section>

            <Section title="Quadro societário">
              {companyData?.socios.length ? (
                <div>
                  {companyData.socios.map((partner, index) => (
                    <div
                      className="flex items-start gap-3 border-b border-border/60 py-3 last:border-0"
                      key={`${partnerName(partner) || "socio"}-${index}`}
                    >
                      <Users className="mt-0.5 size-4 shrink-0 text-primary" />
                      <div className="min-w-0">
                        <p className="break-words text-xs font-medium">
                          {partnerName(partner)}
                        </p>
                        <p className="mt-1 text-[11px] text-muted-foreground">
                          {partnerRole(partner) || "Qualificação não informada"}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <Missing />
              )}
            </Section>

            <Section title="Descrição">
              {item.company_description || item.description ? (
                <p className="text-sm leading-6 text-muted-foreground">
                  {displayDescription(item.company_description || item.description)}
                </p>
              ) : (
                <Missing />
              )}
            </Section>

            {id && (
              <Button asChild className="mt-8 w-full">
                <Link
                  href={`/startups/${encodeURIComponent(id)}`}
                  onClick={(event) => {
                    if (
                      event.defaultPrevented ||
                      event.button !== 0 ||
                      event.metaKey ||
                      event.ctrlKey ||
                      event.shiftKey ||
                      event.altKey
                    ) {
                      return;
                    }
                    startLoading();
                  }}
                >
                  Ver dados completos
                  <ArrowRight className="ml-2 size-4" />
                </Link>
              </Button>
            )}
          </div>
        )}
      </aside>
      {reviewDialogOpen && (
        <ReviewDecisionDialog
          companyName={item?.company_name}
          loading={reviewMutation.isPending}
          onApprove={() => reviewMutation.mutate("APPROVED")}
          onDiscard={() => reviewMutation.mutate("DISCARDED")}
          onClose={() => setReviewDialogOpen(false)}
        />
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-7">
      <h3 className="mb-3 text-xs font-medium text-muted-foreground">{title}</h3>
      {children}
    </section>
  );
}

function DetailLoading() {
  return (
    <div className="grid min-h-[calc(100vh-64px)] place-items-center p-6 text-center">
      <div>
        <LoaderCircle className="mx-auto size-8 animate-spin text-primary" />
        <p className="mt-4 text-sm font-medium">Validando dados da startup</p>
        <p className="mt-2 text-xs leading-5 text-muted-foreground">
          Conferindo fontes, cadastro e evidências antes de abrir a visão geral.
        </p>
      </div>
    </div>
  );
}

function InfoRow({
  label,
  value,
  icon: Icon
}: {
  label: string;
  value?: string | null;
  icon?: typeof MapPin;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border/60 py-2.5 text-xs last:border-0">
      <span className="flex items-center gap-2 text-muted-foreground">
        {Icon && <Icon className="size-3.5" />}
        {label}
      </span>
      <span className={cn("max-w-[55%] text-right", !value && "text-muted-foreground")}>
        {value || "Não informado"}
      </span>
    </div>
  );
}

function Missing() {
  return <p className="text-xs text-muted-foreground">Dados insuficientes.</p>;
}

function displayDescription(value?: string | null) {
  return translateIfEnglish(
    String(value || "")
    .replace(/Descricao original em ingles preservada como evidencia:\s*/gi, "")
    .replace(/Descrição original em inglês preservada como evidência:\s*/gi, "")
    .trim()
  );
}
