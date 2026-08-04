import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(value?: number | null) {
  return typeof value === "number"
    ? new Intl.NumberFormat("pt-BR").format(value)
    : "—";
}

export function formatDate(value?: string | null) {
  if (!value) return "Não informado";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Não informado";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short"
  }).format(date);
}

export function getDomain(url?: string | null) {
  const domain = normalizeDomain(url);
  if (!domain) return "Não informado";
  return domain;
}

export function normalizeDomain(url?: string | null) {
  if (!url) return null;
  const value = url.trim();
  if (!value) return null;

  try {
    const parsed = new URL(value.startsWith("http") ? value : `https://${value}`);
    const domain = parsed.hostname.replace(/^www\./i, "").toLowerCase();
    if (!domain.includes(".") || /\s/.test(domain)) return null;
    return domain;
  } catch {
    return null;
  }
}
