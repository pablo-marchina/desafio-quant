// Gate interno (F5.9) no cliente: a ferramenta e do gerente de Startups & VCs da NVIDIA Brasil,
// nao e publica. O gerente entra com o token compartilhado (TAPI_API_TOKEN) uma vez; ele fica no
// localStorage e acompanha as chamadas a API. O `<AuthGate>` (components/auth-gate.tsx) so pede
// login quando o `/health` diz que a API exige credencial (auth_required) — em dev/offline (sem
// token) nao atrapalha. O token nao vai pro bundle (nada de NEXT_PUBLIC_*): e digitado em runtime.
//
// Duas formas de anexar o token: header (fetch) e query (?token=). O SSE (EventSource) e o PDF
// (<a>) navegam sem poder setar header, entao nesses dois casos o token vai na query — trade-off
// conhecido de ferramenta interna, espelhado no backend (apps/api/deps.py::require_auth).

const TOKEN_KEY = "tapi_token";

// Evento disparado quando uma chamada volta 401 (token ausente/invalido): o AuthGate ouve e
// devolve a UI pro login, sem acoplar os componentes de tela a logica de sessao.
export const UNAUTHORIZED_EVENT = "tapi:unauthorized";

// localStorage so existe no browser; no SSR/prerender (sem window) tudo degrada p/ "sem token".
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}

// Header de auth p/ as chamadas fetch — vazio (sem header) quando nao ha token guardado, o que
// mantem o modo aberto (dev/offline) funcionando sem login.
export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Anexa o token como query (?token=) — p/ EventSource/<a>, que nao mandam header (F5.2/F5.8).
export function appendToken(url: string): string {
  const token = getToken();
  if (!token) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}token=${encodeURIComponent(token)}`;
}

// Limpa o token e avisa o AuthGate (via evento) que a sessao caiu — chamado no 401 das chamadas.
export function signalUnauthorized(): void {
  clearToken();
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  }
}
