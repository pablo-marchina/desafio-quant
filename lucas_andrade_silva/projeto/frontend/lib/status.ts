import { AlertCircle, CheckCircle2, Clock3, XCircle } from "lucide-react";

import type { Startup } from "@/lib/types";

export const validationLabels: Record<string, string> = {
  APPROVED: "Aprovada",
  REVIEW: "Em revisão",
  REJECTED: "Rejeitada",
  DISCARDED: "Descartada",
  Ativa: "Ativa",
  ATIVA: "Ativa",
  Baixada: "Baixada",
  BAIXADA: "Baixada",
  Inapta: "Inapta",
  INAPTA: "Inapta",
  Suspensa: "Suspensa",
  SUSPENSA: "Suspensa",
  Nula: "Nula",
  NULA: "Nula"
};

export const enrichmentLabels: Record<string, string> = {
  enriched: "Enriquecida",
  needs_review: "Requer revisão",
  insufficient_evidence: "Evidência insuficiente",
  error: "Erro",
  discarded: "Descartada",
  scraped: "Coletada"
};

export const aiLabels: Record<string, string> = {
  AI_NATIVE: "AI native",
  AI_ENABLED: "AI enabled",
  AI_MENTIONED: "IA mencionada",
  NON_AI: "Sem IA evidenciada",
  NO_SIGNAL: "Sem sinal de IA",
  INSUFFICIENT_EVIDENCE: "Evidência insuficiente",
  UNKNOWN: "Não classificada"
};

export function normalizeAiClassification(value?: string | null) {
  const normalized = String(value || "").trim().toUpperCase();
  if (normalized === "AI_NATIVE") return "AI_NATIVE";
  if (normalized === "AI_ENABLED" || normalized === "AI_MENTIONED") {
    return "AI_ENABLED";
  }
  if (normalized === "NO_SIGNAL") return "NO_SIGNAL";
  if (normalized === "INSUFFICIENT_EVIDENCE") return "INSUFFICIENT_EVIDENCE";
  if (normalized === "UNKNOWN" || !normalized) return "UNKNOWN";
  return "NON_AI";
}

export function displayAiLabel(value?: string | null) {
  return aiLabels[normalizeAiClassification(value)];
}

export function displayStartupAiLabel(startup?: Startup | null) {
  const normalized = normalizeAiClassification(startup?.ai_dependency_level);
  if (
    (normalized === "NON_AI" || normalized === "NO_SIGNAL" || normalized === "UNKNOWN") &&
    hasEvidenceSource(startup)
  ) {
    return aiLabels.AI_ENABLED;
  }
  return aiLabels[normalized];
}

function hasEvidenceSource(startup?: Startup | null) {
  if (!startup) return false;
  if (
    startup.validated_url ||
    startup.source_url ||
    startup.evidence_text ||
    startup.github_org ||
    startup.technology_intelligence
  ) {
    return true;
  }
  const evidenceUrls = startup.evidence_urls;
  if (Array.isArray(evidenceUrls) && evidenceUrls.length > 0) return true;
  const techStack = toStringList(startup.tech_stack);
  if (techStack.length > 0) return true;
  const identityEvidence = startup.identity_evidence;
  if (
    identityEvidence &&
    typeof identityEvidence === "object" &&
    Object.keys(identityEvidence).length > 0
  ) {
    return true;
  }
  return false;
}

export function statusMeta(status?: string | null) {
  switch (status) {
    case "APPROVED":
    case "enriched":
    case "scraped":
    case "Ativa":
    case "ATIVA":
      return {
        label:
          validationLabels[status] ||
          enrichmentLabels[status] ||
          status,
        className: "border-primary/20 bg-primary/10 text-primary",
        Icon: CheckCircle2
      };
    case "REVIEW":
    case "needs_review":
    case "insufficient_evidence":
      return {
        label: validationLabels[status] || enrichmentLabels[status],
        className: "border-warning/20 bg-warning/10 text-warning",
        Icon: Clock3
      };
    case "REJECTED":
    case "DISCARDED":
    case "discarded":
    case "error":
    case "Baixada":
    case "BAIXADA":
    case "Inapta":
    case "INAPTA":
    case "Suspensa":
    case "SUSPENSA":
    case "Nula":
    case "NULA":
      return {
        label:
          validationLabels[status] ||
          enrichmentLabels[status] ||
          "Erro",
        className: "border-destructive/20 bg-destructive/10 text-destructive",
        Icon: XCircle
      };
    default:
      return {
        label: "Não informado",
        className: "border-border bg-white/[0.03] text-muted-foreground",
        Icon: AlertCircle
      };
  }
}

export function toStringList(value?: string[] | string | null): string[] {
  if (Array.isArray(value)) return value.filter(Boolean);
  if (typeof value !== "string" || !value.trim()) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.filter(Boolean).map(String) : [value];
  } catch {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
}
