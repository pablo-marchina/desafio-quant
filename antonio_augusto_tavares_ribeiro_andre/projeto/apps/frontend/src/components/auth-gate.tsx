"use client";

// Gate interno da UI (F5.9): a ferramenta e do gerente de Startups & VCs da NVIDIA Brasil, nao e
// publica. No boot consulta `GET /health` (aberto): se a API exige credencial (auth_required) e
// nao ha token guardado, pede login antes de mostrar qualquer tela; em dev/offline (sem token) a
// UI abre direto, sem atrito. Um 401 em qualquer chamada (token revogado/errado) devolve a UI pro
// login via o evento global (lib/auth.ts::signalUnauthorized); espelha o gate do backend
// (apps/api/deps.py::require_auth).

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { fetchHealth, pingAuth } from "@/lib/api";
import { getToken, setToken, clearToken, UNAUTHORIZED_EVENT } from "@/lib/auth";

// checking: sondando /health · open: API sem gate · unlocked: gate + token aceito ·
// locked: gate sem token (pede login) · error: /health fora do ar.
type GateState = "checking" | "open" | "unlocked" | "locked" | "error";

// Mapeia o /health no estado do gate: API sem token = aberta; com token, depende de ja haver
// credencial guardada. Fica fora do componente — sem setState sincrono, so resolve a Promise.
function resolveGate(): Promise<GateState> {
  return fetchHealth().then((h) =>
    !h.auth_required ? "open" : getToken() ? "unlocked" : "locked",
  );
}

export function AuthGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<GateState>("checking");

  // Sonda o /health no boot e decide o estado inicial. O setState vive so nos callbacks async
  // (evita o react-hooks/set-state-in-effect) e e guardado contra desmonte.
  useEffect(() => {
    let alive = true;
    resolveGate()
      .then((s) => alive && setState(s))
      .catch(() => alive && setState("error"));
    return () => {
      alive = false;
    };
  }, []);

  // Um 401 em qualquer chamada da API limpa o token e dispara este evento — volta pro login.
  useEffect(() => {
    const onUnauthorized = () => setState("locked");
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  // Retry do estado de erro: roda num event handler (nao no effect), entao pode mostrar "checking".
  function retry() {
    setState("checking");
    resolveGate()
      .then(setState)
      .catch(() => setState("error"));
  }

  if (state === "open" || state === "unlocked") {
    return <>{children}</>;
  }

  if (state === "error") {
    return (
      <Centered>
        <p className="text-sm text-muted-foreground">
          Nao foi possivel falar com a API. Verifique se o backend (F5.2) esta no ar.
        </p>
        <Button onClick={retry} variant="outline" size="sm">
          Tentar de novo
        </Button>
      </Centered>
    );
  }

  if (state === "locked") {
    return <LoginForm onSuccess={() => setState("unlocked")} />;
  }

  // checking
  return (
    <Centered>
      <span className="size-5 animate-spin rounded-full border-2 border-muted border-t-foreground" />
      <p className="text-sm text-muted-foreground">Verificando acesso...</p>
    </Centered>
  );
}

// Login do gate (F5.9): o gerente cola o token compartilhado; validamos contra um endpoint
// protegido (pingAuth) p/ dar feedback imediato antes de liberar a UI.
function LoginForm({ onSuccess }: { onSuccess: () => void }) {
  const [value, setValue] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const token = value.trim();
    if (!token || submitting) return;

    setSubmitting(true);
    setError(null);
    setToken(token);
    try {
      if (await pingAuth()) {
        onSuccess();
        return;
      }
      clearToken();
      setError("Credencial recusada. Confira o token de acesso.");
    } catch (err) {
      clearToken();
      setError(err instanceof Error ? err.message : "Falha ao validar a credencial.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Centered>
      <form
        onSubmit={submit}
        className="flex w-full max-w-sm flex-col gap-4 rounded-lg border border-border bg-card p-6 text-card-foreground"
      >
        <div className="flex flex-col gap-1">
          <span className="inline-flex w-fit items-center rounded-full border border-border px-3 py-1 text-xs font-medium text-muted-foreground">
            NVIDIA Inception · ferramenta interna
          </span>
          <h1 className="mt-2 text-lg font-semibold">Acesso restrito</h1>
          <p className="text-sm text-muted-foreground">
            Esta ferramenta e interna do gerente de Startups &amp; VCs. Informe o token de acesso.
          </p>
        </div>

        <input
          type="password"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Token de acesso"
          autoFocus
          disabled={submitting}
          className="h-9 rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
        />

        {error && <p className="text-sm text-destructive">{error}</p>}

        <Button type="submit" variant="brand" disabled={submitting || value.trim() === ""}>
          {submitting ? "Validando..." : "Entrar"}
        </Button>
      </form>
    </Centered>
  );
}

// Casca centralizada (tela cheia) compartilhada pelos estados de loading/erro/login do gate.
function Centered({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen flex-1 flex-col items-center justify-center gap-4 bg-background px-6 text-foreground">
      {children}
    </main>
  );
}
