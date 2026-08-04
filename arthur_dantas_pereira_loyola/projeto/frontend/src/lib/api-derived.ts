import type { RunSummary, StartupRecord } from "@/lib/api";

export type MaturityLabel = "AI-Native" | "AI-Enabled" | "Non-AI";

export function parseListField(value: string | null | undefined): string[] {
  if (!value) return [];
  const trimmed = value.trim();
  if (!trimmed) return [];
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (Array.isArray(parsed)) {
      return parsed.filter(
        (item): item is string =>
          typeof item === "string" && item.trim().length > 0,
      );
    }
  } catch {
    // Fall back to comma splitting for legacy rows.
  }
  return trimmed
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function maturityLabel(
  value: string | null | undefined,
): MaturityLabel | null {
  if (value === "AI-Native" || value === "AI-Enabled" || value === "Non-AI")
    return value;
  return null;
}

export function scoreFromConfidence(value: number | null | undefined): number {
  if (typeof value !== "number" || Number.isNaN(value)) return 0;
  const normalized = value <= 1 ? value * 100 : value;
  return Math.round(Math.min(100, Math.max(0, normalized)));
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function unavailable(value: string | null | undefined): string {
  return value && value.trim() ? value : "Nao disponivel";
}

export function findLatestRunForStartup(
  startup: StartupRecord | undefined,
  runs: RunSummary[],
): RunSummary | null {
  if (!startup || runs.length === 0) return null;
  const normalizedName = normalize(startup.name);
  const candidates = runs.filter((run) => {
    if (run.startup_id === startup.id) return true;
    const query = normalize(run.query);
    return query.includes(normalizedName) || normalizedName.includes(query);
  });

  return (
    [...candidates].sort((a, b) => runTimestamp(b) - runTimestamp(a))[0] ?? null
  );
}

export function normalize(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function runTimestamp(run: RunSummary): number {
  const value = run.completed_at ?? run.created_at;
  const timestamp = new Date(value).getTime();
  return Number.isNaN(timestamp) ? 0 : timestamp;
}
