import type { UrlIngestionStatus } from "@/lib/api/radar-types";

export const ORDERED_STATUSES: UrlIngestionStatus[] = ["pending", "scraping", "ingesting", "embedding", "analyzing", "completed"];

export const STATUS_LABELS: Record<UrlIngestionStatus, string> = {
  pending: "Na fila", scraping: "Coletando fonte", ingesting: "Preparando documento",
  embedding: "Indexando conhecimento", analyzing: "Gerando analise", completed: "Concluida", failed: "Falhou",
};
