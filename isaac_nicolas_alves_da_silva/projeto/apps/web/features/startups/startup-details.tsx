"use client";

import { useState } from "react";
import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";

import { MarkdownContent } from "@/components/markdown-content";
import {
  getStartup,
  getStartupEvidences,
  listBriefings,
  listRecommendations,
  refreshStartupAnalysis,
  reviewBriefing,
  reviewRecommendation,
} from "@/lib/api/radar-client";
import type { Briefing, Recommendation, ReviewInput, Startup, StartupAIProfile, StartupEvidence } from "@/lib/api/radar-types";

function Field({ label, value }: { label: string; value: string | null }) {
  const displayValue = !value || value === "unknown" ? "Nao informado" : value;
  return <div><dt className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{label}</dt><dd className="mt-1">{displayValue}</dd></div>;
}

const REVIEW_LABELS: Record<ReviewInput["status"], string> = {
  pending: "Pendente",
  approved: "Aprovado",
  rejected: "Rejeitado",
};

const REVIEW_CLASSES: Record<ReviewInput["status"], string> = {
  pending: "bg-[#20334d] text-[var(--muted)]",
  approved: "bg-[#183414] text-[var(--accent)]",
  rejected: "bg-[#4a1e25] text-[#ff9cab]",
};

const FIT_BADGE_TONE_CLASSES: Record<"ready" | "qualifying" | "needs-evidence", string> = {
  ready: "bg-[#183414] text-[var(--accent)]",
  qualifying: "bg-[#3a2c14] text-[#e8b84b]",
  "needs-evidence": "bg-[#20334d] text-[var(--muted)]",
};

/** Regra simples sobre dados que ja existem - sem chamada nova a API. */
function computeFitBadge(startup: Startup, recommendations: Recommendation[], briefing: Briefing | undefined) {
  const bestScore = recommendations.reduce((max, recommendation) => Math.max(max, recommendation.score), 0);
  if (startup.ai_maturity_level === "ai_native" && bestScore >= 0.5 && briefing) {
    return { label: "Pronto para contato", tone: "ready" as const };
  }
  if (bestScore >= 0.25) {
    return { label: "Em qualificacao", tone: "qualifying" as const };
  }
  return { label: "Precisa mais evidencia", tone: "needs-evidence" as const };
}

function compactText(value: string | null | undefined, maxLength = 520) {
  const normalized = value?.replace(/\s+/g, " ").trim();
  if (!normalized) return null;
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength).trim()}...`;
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

const EVIDENCE_SIGNAL_PATTERNS = [
  { label: "AI", pattern: /\b(ai|artificial intelligence|inteligencia artificial|inteligência artificial)\b/i },
  { label: "Agentes", pattern: /\b(agent|agents|agente|agentes|custom agents?)\b/i },
  { label: "LLM", pattern: /\b(llm|large language model|model provider|modelo de linguagem)\b/i },
  { label: "Automacao", pattern: /\b(automate|automation|automacao|automação|repetitive tasks|workflow)\b/i },
  { label: "Busca enterprise", pattern: /\b(enterprise search|search across|busca|connectors?)\b/i },
  { label: "Meeting notes", pattern: /\b(meeting notes|transcribe|summarize|reunioes|reuniões)\b/i },
  { label: "Governanca", pattern: /\b(governance|governanca|governança|admin controls|permissions|controls)\b/i },
  { label: "Seguranca", pattern: /\b(security|seguranca|segurança|soc 2|iso 27001|gdpr|hipaa|encryption)\b/i },
];

function evidenceSignals(text: string) {
  return EVIDENCE_SIGNAL_PATTERNS.filter(({ pattern }) => pattern.test(text))
    .map(({ label }) => label)
    .slice(0, 6);
}

const EVIDENCE_SECTION_RULES = [
  { title: "Sinais de IA", pattern: /\b(ai|artificial intelligence|notion ai|agent|agents|custom agents?|llm|generative|machine learning|model agnostic)\b/i },
  { title: "Produto e workflow", pattern: /\b(workspace|docs|projects|meeting notes|enterprise search|calendar|mail|slack|github|google drive|workflow|tasks|reports|databases)\b/i },
  { title: "Seguranca e governanca", pattern: /\b(security|governance|admin controls|permissions|saml|sso|soc 2|iso 27001|gdpr|ccpa|hipaa|encryption|zero data retention|no training)\b/i },
  { title: "Comercial e escala", pattern: /\b(enterprise|business|pricing|credits|trusted by|customers|teams|startups|small businesses|free to try|contact sales)\b/i },
];

function evidenceSentences(text: string) {
  return text
    .replace(/\s+/g, " ")
    .trim()
    .split(/(?<=[.!?])\s+|(?=\b(?:Notion Agent|Custom Agents|Enterprise Search|AI Meeting Notes|No training|SOC 2|GDPR|HIPAA|What can|How does|How much)\b)/)
    .map((sentence) => sentence.trim())
    .filter((sentence) => sentence.length >= 24);
}

function evidenceSections(text: string) {
  const sentences = evidenceSentences(text);
  const used = new Set<string>();
  const sections = EVIDENCE_SECTION_RULES.map(({ title, pattern }) => {
    const items = sentences
      .filter((sentence) => pattern.test(sentence))
      .filter((sentence) => {
        if (used.has(sentence)) return false;
        used.add(sentence);
        return true;
      })
      .slice(0, 2)
      .map((sentence) => compactText(sentence, 160) || sentence);

    return { title, items };
  }).filter((section) => section.items.length > 0);

  if (sections.length > 0) return sections;

  const fallback = compactText(text, 220);
  return fallback ? [{ title: "Resumo", items: [fallback] }] : [];
}

function MetricPill({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "accent" | "neutral" | "warning" }) {
  const toneClass = {
    accent: "border-[var(--accent)]/40 bg-[var(--accent)]/10 text-[var(--accent)]",
    neutral: "border-[var(--surface-border)] bg-[#07111f] text-[var(--muted)]",
    warning: "border-[#e8b84b]/40 bg-[#3a2c14] text-[#e8b84b]",
  }[tone];

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${toneClass}`}>
      <span className="text-[10px] font-semibold uppercase tracking-wide opacity-80">{label}</span>
      <span className="font-semibold">{value}</span>
    </span>
  );
}

function EvidenceCard({ evidence }: { evidence: StartupEvidence }) {
  const [expanded, setExpanded] = useState(false);
  const text = evidence.notes || "Evidencia coletada e aprovada pelo pipeline.";
  const sections = evidenceSections(text);
  const signals = evidenceSignals(text);
  const shouldShowRaw = text.replace(/\s+/g, " ").trim().length > 280;

  return (
    <article className="border-t border-[var(--surface-border)] py-4 first:border-t-0 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <a className="font-medium text-[var(--accent)] underline underline-offset-4" href={evidence.source_url} rel="noreferrer" target="_blank">
            {evidence.title || evidence.source_url}
          </a>
          <p className="mt-1 text-xs uppercase tracking-wide text-[var(--muted)]">{evidence.evidence_type.replaceAll("_", " ")}</p>
        </div>
        {evidence.confidence_score !== null && evidence.confidence_score !== undefined ? (
          <MetricPill label="fonte" value={formatPercent(evidence.confidence_score)} tone="accent" />
        ) : null}
      </div>
      {signals.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {signals.map((signal) => (
            <span className="rounded-full bg-[#20334d] px-2 py-1 text-xs text-[var(--muted)]" key={signal}>{signal}</span>
          ))}
        </div>
      ) : null}
      <div className="mt-4 grid gap-3">
        {sections.map((section) => (
          <div className="rounded-md border border-[var(--surface-border)] bg-[#07111f] p-3" key={section.title}>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--muted)]">{section.title}</p>
            <ul className="mt-2 space-y-1.5 text-sm leading-6 text-[var(--fg)]">
              {section.items.map((item) => (
                <li className="grid grid-cols-[8px_1fr] gap-2" key={item}>
                  <span className="mt-2 h-1.5 w-1.5 rounded-full bg-[var(--accent)]" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      {shouldShowRaw ? (
        <button className="mt-2 text-xs font-semibold text-[var(--accent)] underline underline-offset-4" onClick={() => setExpanded((current) => !current)} type="button">
          {expanded ? "Ocultar texto bruto" : "Ver texto bruto"}
        </button>
      ) : null}
      {expanded ? (
        <div className="mt-3 max-h-64 overflow-auto rounded-md border border-[var(--surface-border)] bg-[#050b14] p-3 text-xs leading-5 text-[var(--muted)]">
          {text}
        </div>
      ) : null}
    </article>
  );
}

function ReviewControls({
  currentStatus,
  currentComment,
  reviewedBy,
  reviewedAt,
  isPending,
  onReview,
}: {
  currentStatus: ReviewInput["status"];
  currentComment: string | null;
  reviewedBy: string | null;
  reviewedAt: string | null;
  isPending: boolean;
  onReview: (input: ReviewInput) => void;
}) {
  const [comment, setComment] = useState(currentComment ?? "");
  const [reviewer, setReviewer] = useState(reviewedBy ?? "");
  const submit = (status: ReviewInput["status"]) => {
    onReview({
      status,
      comment: comment.trim() || undefined,
      reviewed_by: reviewer.trim() || undefined,
    });
  };

  return (
    <div className="mt-4 border-t border-[var(--surface-border)] pt-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${REVIEW_CLASSES[currentStatus]}`}>
          {REVIEW_LABELS[currentStatus]}
        </span>
        {reviewedAt ? <span className="text-xs text-[var(--muted)]">Revisado por {reviewedBy || "analista"} em {new Date(reviewedAt).toLocaleDateString("pt-BR")}</span> : null}
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_180px]">
        <input
          className="rounded-md border border-[var(--surface-border)] bg-[#07111f] px-3 py-2 text-sm"
          onChange={(event) => setComment(event.target.value)}
          placeholder="Comentario da revisao"
          type="text"
          value={comment}
        />
        <input
          className="rounded-md border border-[var(--surface-border)] bg-[#07111f] px-3 py-2 text-sm"
          onChange={(event) => setReviewer(event.target.value)}
          placeholder="Revisor"
          type="text"
          value={reviewer}
        />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button className="rounded-md bg-[var(--accent)] px-3 py-2 text-xs font-semibold text-[#07111f] disabled:opacity-60" disabled={isPending} onClick={() => submit("approved")} type="button">Aprovar</button>
        <button className="rounded-md border border-[#ff9cab] px-3 py-2 text-xs font-semibold text-[#ff9cab] disabled:opacity-60" disabled={isPending} onClick={() => submit("rejected")} type="button">Rejeitar</button>
        <button className="rounded-md border border-[var(--surface-border)] px-3 py-2 text-xs font-semibold text-[var(--muted)] disabled:opacity-60" disabled={isPending} onClick={() => submit("pending")} type="button">Reabrir</button>
      </div>
    </div>
  );
}

const FIELD_LABELS: Record<string, string> = {
  founders: "Fundadores",
  funding_stage: "Estágio de funding",
  funding_amount_usd: "Valor captado",
  customers: "Clientes",
  sector: "Setor",
  description: "Descrição",
};

function FieldAuditSection({
  fieldConfidence,
  fieldEvidenceIds,
}: {
  fieldConfidence: Record<string, number>;
  fieldEvidenceIds: Record<string, string[]>;
}) {
  const entries = Object.entries(fieldConfidence).filter(([key]) => key in FIELD_LABELS);
  if (entries.length === 0) return null;

  return (
    <div className="mt-6 border-t border-[var(--surface-border)] pt-6">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Rastreabilidade de Extração</h3>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {entries.map(([field, confidence]) => {
          const pct = Math.round(confidence * 100);
          const color = pct >= 80 ? "bg-[var(--accent)]" : pct >= 50 ? "bg-yellow-400" : "bg-red-400";
          const evidenceCount = fieldEvidenceIds[field]?.length ?? 0;
          return (
            <div className="rounded-md border border-[var(--surface-border)] p-3" key={field}>
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-[var(--muted)]">{FIELD_LABELS[field] ?? field}</span>
                <span className="tabular-nums text-[var(--fg)]">{pct}%</span>
              </div>
              <div className="mt-2 h-1.5 w-full rounded-full bg-[#20334d]">
                <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
              </div>
              {evidenceCount > 0 && (
                <p className="mt-1.5 text-[10px] text-[var(--muted)]">{evidenceCount} evidência{evidenceCount > 1 ? "s" : ""} de suporte</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AIProfileSection({ profile }: { profile: StartupAIProfile }) {
  const knownFields = [
    { label: "Workload de IA", value: profile.ai_workload_type },
    { label: "Tipo de modelo", value: profile.model_type },
    { label: "Modalidade de dados", value: profile.data_modality },
    { label: "Estágio de deploy", value: profile.deployment_stage },
    { label: "Infraestrutura", value: profile.infra_environment },
    { label: "Necessidade de GPU", value: profile.gpu_need },
    { label: "Latência", value: profile.latency_requirement },
  ].filter(({ value }) => value && value !== "unknown");

  if (knownFields.length === 0 && !profile.business_goal && profile.current_tools.length === 0) return null;

  return (
    <div className="mt-6 border-t border-[var(--surface-border)] pt-6">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Perfil de IA</h3>
      <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {knownFields.map(({ label, value }) => (
          <div key={label}>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{label}</dt>
            <dd className="mt-1 text-sm">{value}</dd>
          </div>
        ))}
        {profile.scale_signal && (
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Sinal de escala</dt>
            <dd className="mt-1 text-sm">{profile.scale_signal}</dd>
          </div>
        )}
        {profile.business_goal && (
          <div className="sm:col-span-2">
            <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Objetivo de negócio</dt>
            <dd className="mt-1 text-sm">{profile.business_goal}</dd>
          </div>
        )}
      </dl>
      {profile.current_tools.length > 0 && (
        <div className="mt-4">
          <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Stack atual</dt>
          <dd className="mt-2 flex flex-wrap gap-2">
            {profile.current_tools.map((tool) => (
              <span className="rounded-full bg-[#20334d] px-2 py-1 text-xs text-[var(--muted)]" key={tool}>{tool}</span>
            ))}
          </dd>
        </div>
      )}
    </div>
  );
}

function RecommendationCard({ recommendation, evidences, startupId }: { recommendation: Recommendation; evidences: StartupEvidence[]; startupId: string }) {
  const [expanded, setExpanded] = useState(false);
  const queryClient = useQueryClient();
  const matchedEvidences = evidences.filter((evidence) => recommendation.evidence_ids.includes(evidence.id));
  const reviewMutation = useMutation({
    mutationFn: (input: ReviewInput) => reviewRecommendation(recommendation.id, input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["recommendations", startupId] });
    },
  });

  const complexityLabel: Record<string, string> = { low: "Baixa", medium: "Média", high: "Alta" };
  const complexityColor: Record<string, string> = {
    low: "bg-green-900/40 text-green-300",
    medium: "bg-yellow-900/40 text-yellow-300",
    high: "bg-red-900/40 text-red-300",
  };
  const nivelLabel: Record<string, string> = { forte: "Forte", moderada: "Moderada", exploratoria: "Exploratória" };
  const nivelColor: Record<string, string> = {
    forte: "bg-green-900/60 text-green-200 border border-green-700",
    moderada: "bg-blue-900/40 text-blue-300 border border-blue-700",
    exploratoria: "bg-neutral-800 text-neutral-400 border border-neutral-600",
  };

  return (
    <article className="rounded-lg border border-[var(--surface-border)] bg-[#07111f] p-4">
      <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-[var(--surface-border)] px-2 py-0.5 text-xs font-bold text-[var(--muted)]">#{recommendation.priority}</span>
            <h3 className="text-base font-semibold">{recommendation.technology_name}</h3>
            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${nivelColor[recommendation.nivel] ?? nivelColor.exploratoria}`}>
              {nivelLabel[recommendation.nivel] ?? recommendation.nivel}
            </span>
          </div>
          <MarkdownContent className="mt-3 max-w-3xl text-sm leading-6 text-[var(--muted)] [&_p]:mt-0" content={recommendation.justification} />
        </div>
        <div className="flex min-w-[150px] flex-row gap-2 sm:flex-col sm:items-end">
          <div className="rounded-md border border-[var(--accent)]/30 bg-[var(--accent)]/10 px-3 py-2 text-right">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--muted)]">Fit</p>
            <p className="text-2xl font-semibold text-[var(--accent)]">{formatPercent(recommendation.score)}</p>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${complexityColor[recommendation.complexity] ?? complexityColor.medium}`}>
            {complexityLabel[recommendation.complexity] ?? recommendation.complexity}
          </span>
          <span className="text-xs text-[var(--muted)]" title="Confianca baseada na qualidade e especificidade das evidencias">
            {formatPercent(recommendation.confidence)} conf. evid.
          </span>
        </div>
      </div>
      </div>
      {recommendation.faltando && recommendation.faltando.length > 0 && (
        <div className="mt-4 rounded-md border border-[#e8b84b]/30 bg-[#3a2c14] px-3 py-2 text-xs leading-5 text-[#e8b84b]">
          <span className="font-semibold">Para elevar: </span>
          {recommendation.faltando.join(" · ")}
        </div>
      )}
      {recommendation.signal_origins && recommendation.signal_origins.length > 0 && (
        <div className="mt-3 text-xs leading-5 text-[var(--muted)]">
          <span className="font-semibold">Sinais: </span>
          {recommendation.signal_origins.join(" · ")}
        </div>
      )}
      {recommendation.matched_keywords.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {recommendation.matched_keywords.map((keyword) => <span className="rounded-full bg-[#20334d] px-2 py-1 text-xs text-[var(--muted)]" key={keyword}>{keyword}</span>)}
        </div>
      )}
      <button className="mt-4 text-xs font-semibold text-[var(--accent)] underline underline-offset-4" onClick={() => setExpanded((current) => !current)} type="button">
        {expanded ? "Ocultar evidencia" : "Ver evidencia"}
      </button>
      {expanded && (
        <div className="mt-3 space-y-2 border-t border-[var(--surface-border)] pt-3">
          {matchedEvidences.length ? matchedEvidences.map((evidence) => (
            <a className="block text-sm text-[var(--accent)] underline" href={evidence.source_url} key={evidence.id} rel="noreferrer" target="_blank">
              {evidence.title || evidence.source_url}
            </a>
          )) : <p className="text-sm text-[var(--muted)]">Sem evidencia especifica vinculada a esta recomendacao.</p>}
        </div>
      )}
      <ReviewControls
        currentComment={recommendation.review_comment}
        currentStatus={recommendation.review_status}
        isPending={reviewMutation.isPending}
        onReview={(input) => reviewMutation.mutate(input)}
        reviewedAt={recommendation.reviewed_at}
        reviewedBy={recommendation.reviewed_by}
      />
      {reviewMutation.isError ? <p className="mt-2 text-sm text-[var(--danger)]">{reviewMutation.error.message}</p> : null}
    </article>
  );
}

function BriefingReviewPanel({ briefing, startupId }: { briefing: Briefing; startupId: string }) {
  const queryClient = useQueryClient();
  const reviewMutation = useMutation({
    mutationFn: (input: ReviewInput) => reviewBriefing(briefing.id, input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["briefings", startupId] });
    },
  });

  return (
    <>
      <ReviewControls
        currentComment={briefing.review_comment}
        currentStatus={briefing.review_status}
        isPending={reviewMutation.isPending}
        onReview={(input) => reviewMutation.mutate(input)}
        reviewedAt={briefing.reviewed_at}
        reviewedBy={briefing.reviewed_by}
      />
      {reviewMutation.isError ? <p className="mt-2 text-sm text-[var(--danger)]">{reviewMutation.error.message}</p> : null}
    </>
  );
}

export function StartupDetails({ startupId }: { startupId: string }) {
  const queryClient = useQueryClient();
  const [startupQuery, evidencesQuery, recommendationsQuery, briefingsQuery] = useQueries({
    queries: [
      { queryKey: ["startup", startupId], queryFn: () => getStartup(startupId) },
      { queryKey: ["startup-evidences", startupId], queryFn: () => getStartupEvidences(startupId) },
      { queryKey: ["recommendations", startupId], queryFn: () => listRecommendations(startupId) },
      { queryKey: ["briefings", startupId], queryFn: () => listBriefings(startupId) },
    ],
  });
  const refreshMutation = useMutation({
    mutationFn: () => refreshStartupAnalysis(startupId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["recommendations", startupId] }),
        queryClient.invalidateQueries({ queryKey: ["briefings", startupId] }),
      ]);
    },
  });

  if (startupQuery.isLoading) return <p className="mt-8 text-[var(--muted)]">Carregando resultado...</p>;
  if (startupQuery.isError) return <p className="mt-8 rounded-md border border-[var(--danger)] p-4 text-[var(--danger)]">{startupQuery.error.message}</p>;

  const startup = startupQuery.data;
  if (!startup) return <p className="mt-8 text-[var(--muted)]">Startup nao encontrada.</p>;
  const evidences = evidencesQuery.data ?? [];
  const recommendations = recommendationsQuery.data ?? [];
  const briefing = briefingsQuery.data?.[0];
  const fallbackDescription = evidences[0]?.notes?.replace(/\s+/g, " ").slice(0, 420);
  const fitBadge = computeFitBadge(startup, recommendations, briefing);

  return (
    <div className="mt-6 space-y-8">
      <section className="rounded-xl border border-[var(--surface-border)] bg-[var(--surface)] p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div><h1 className="text-3xl font-semibold">{startup.name}</h1><p className="mt-2 max-w-3xl text-[var(--muted)]">{startup.description || fallbackDescription || "Descricao ainda nao disponivel."}</p></div>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-3 py-1 text-sm font-semibold ${FIT_BADGE_TONE_CLASSES[fitBadge.tone]}`}>{fitBadge.label}</span>
            {startup.ai_maturity_level && <span className="rounded-full bg-[var(--accent)] px-3 py-1 text-sm font-semibold text-[#07111f]">{startup.ai_maturity_level.replaceAll("_", " ")}</span>}
          </div>
        </div>
        <dl className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Setor" value={startup.sector} /><Field label="Pais" value={startup.country} />
          <Field label="Funding" value={startup.funding_stage} /><Field label="Fundadores" value={startup.founders.join(", ") || null} />
          <Field label="Clientes" value={startup.customers.join(", ") || null} />
        </dl>
        {startup.ai_profile && <AIProfileSection profile={startup.ai_profile} />}
        <FieldAuditSection fieldConfidence={startup.field_confidence} fieldEvidenceIds={startup.field_evidence_ids} />
        {startup.website_url && <a className="mt-6 inline-block text-sm text-[var(--accent)] underline" href={startup.website_url} rel="noreferrer" target="_blank">Abrir fonte principal</a>}
      </section>

      <section className="grid gap-8 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.35fr)]">
        <div className="rounded-xl border border-[var(--surface-border)] bg-[var(--surface)] p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-xl font-semibold">Evidencias</h2>
            <MetricPill label="fontes" value={String(evidences.length)} />
          </div>
          <div className="mt-5">{evidences.length ? evidences.map((evidence) => <EvidenceCard evidence={evidence} key={evidence.id} />) : <p className="text-[var(--muted)]">Nenhuma evidencia disponivel.</p>}</div>
        </div>
        <div className="rounded-xl border border-[var(--surface-border)] bg-[var(--surface)] p-6">
          <h2 className="text-xl font-semibold">Recomendacoes NVIDIA</h2>
          {recommendations.length === 0 ? (
            <p className="mt-5 text-[var(--muted)]">Nenhuma recomendacao foi gerada.</p>
          ) : (() => {
            const strong = recommendations.filter((r) => r.nivel === "forte");
            const exploratory = recommendations.filter((r) => r.nivel !== "forte");
            return (
              <div className="mt-5 space-y-8">
                <div>
                  <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--accent)]">Recomendacoes Fortes</h3>
                  {strong.length > 0 ? (
                    <div className="space-y-4">
                      {strong.map((r) => <RecommendationCard evidences={evidences} key={r.id} recommendation={r} startupId={startupId} />)}
                    </div>
                  ) : (
                    <p className="text-sm text-[var(--muted)]">Nenhuma recomendacao forte com as evidencias atuais.</p>
                  )}
                </div>
                {exploratory.length > 0 && (
                  <div>
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Hipoteses Exploratorias</h3>
                    <div className="space-y-4">
                      {exploratory.map((r) => <RecommendationCard evidences={evidences} key={r.id} recommendation={r} startupId={startupId} />)}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      </section>

      <section className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-[var(--surface-border)] bg-[var(--surface)] p-6">
        <div><h2 className="text-xl font-semibold">Atualizar analise</h2><p className="mt-1 text-sm text-[var(--muted)]">Recalcula as recomendacoes com as regras atuais e regenera o briefing.</p></div>
        <div className="text-right"><button className="rounded-md bg-[var(--accent)] px-5 py-3 font-semibold text-[#07111f] disabled:cursor-not-allowed disabled:opacity-60" disabled={refreshMutation.isPending} onClick={() => refreshMutation.mutate()} type="button">{refreshMutation.isPending ? "Atualizando..." : "Atualizar recomendacoes"}</button>{refreshMutation.isError && <p className="mt-2 text-sm text-[var(--danger)]">{refreshMutation.error.message}</p>}</div>
      </section>

      <section className="rounded-xl border border-[var(--surface-border)] bg-[var(--surface)] p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h2 className="text-xl font-semibold">Briefing executivo</h2>
          {briefing && <a className="rounded-md border border-[var(--surface-border)] px-4 py-2 text-sm font-semibold text-[var(--accent)]" href={`/api/radar/briefings/${briefing.id}/export`}>Exportar PDF</a>}
        </div>
        {briefing ? (
          <>
            <MarkdownContent className="mt-5 text-[var(--muted)]" content={briefing.content} />
            <BriefingReviewPanel briefing={briefing} startupId={startupId} />
          </>
        ) : <p className="mt-5 text-[var(--muted)]">Briefing ainda nao disponivel.</p>}
      </section>
    </div>
  );
}
