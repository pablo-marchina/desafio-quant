import { useSyncExternalStore } from "react";

export type ContactStatus =
  | "Não contactada"
  | "Contactada"
  | "Aguardando resposta"
  | "Em negociação"
  | "Contrato fechado"
  | "Contrato recusado";

export const CONTACT_STATUSES: ContactStatus[] = [
  "Não contactada",
  "Contactada",
  "Aguardando resposta",
  "Em negociação",
  "Contrato fechado",
  "Contrato recusado",
];

export interface ContactRecord {
  status: ContactStatus;
  updatedAt: string; // ISO
  note?: string;
}

const KEY = "toph.contacts.v1";

type State = Record<string, ContactRecord>;

const initial: State = {
  neurabra: { status: "Em negociação", updatedAt: "2026-06-18T10:12:00Z", note: "Discovery técnica agendada com VP Eng." },
  "vortex-vision": { status: "Contactada", updatedAt: "2026-06-15T14:30:00Z", note: "Primeiro e-mail enviado." },
  "lumini-health": { status: "Aguardando resposta", updatedAt: "2026-06-10T09:00:00Z" },
  omnigen: { status: "Contrato fechado", updatedAt: "2026-05-28T16:45:00Z", note: "Onboarding Inception concluído." },
  "quanta-logix": { status: "Contrato recusado", updatedAt: "2026-04-20T11:00:00Z", note: "Sem fit comercial neste ciclo." },
};

let state: State = load();
const listeners = new Set<() => void>();

function load(): State {
  if (typeof window === "undefined") return { ...initial };
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return { ...initial };
    return { ...initial, ...JSON.parse(raw) };
  } catch {
    return { ...initial };
  }
}

function persist() {
  if (typeof window === "undefined") return;
  try { window.localStorage.setItem(KEY, JSON.stringify(state)); } catch {}
}

function emit() {
  for (const l of listeners) l();
}

export function setContactStatus(id: string, status: ContactStatus, note?: string) {
  state = {
    ...state,
    [id]: {
      status,
      updatedAt: new Date().toISOString(),
      note: note ?? state[id]?.note,
    },
  };
  persist();
  emit();
}

export function getContactRecord(id: string): ContactRecord {
  return state[id] ?? { status: "Não contactada", updatedAt: "" };
}

export function useContacts(): State {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => state,
    () => initial,
  );
}

export function useContact(id: string): ContactRecord {
  const all = useContacts();
  return all[id] ?? { status: "Não contactada", updatedAt: "" };
}

export const STATUS_COLORS: Record<ContactStatus, string> = {
  "Não contactada": "border-border bg-muted text-muted-foreground",
  "Contactada": "border-info/40 bg-info/10 text-info",
  "Aguardando resposta": "border-warning/40 bg-warning/10 text-warning",
  "Em negociação": "border-primary/40 bg-primary/10 text-primary",
  "Contrato fechado": "border-primary/40 bg-primary/15 text-primary",
  "Contrato recusado": "border-destructive/40 bg-destructive/10 text-destructive",
};
