"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { listStartups } from "@/lib/api/radar-client";

const PAGE_SIZE = 12;

function maturityLabel(value: string | null) {
  return value ? value.replaceAll("_", " ") : "nao classificada";
}

export function StartupPortfolio() {
  const [page, setPage] = useState(1);
  const [draftQuery, setDraftQuery] = useState("");
  const [query, setQuery] = useState("");
  const [sector, setSector] = useState("");
  const [country, setCountry] = useState("");
  const [maturity, setMaturity] = useState("");
  const params = { page, page_size: PAGE_SIZE, query, sector, country, ai_maturity_level: maturity };
  const startupsQuery = useQuery({
    queryKey: ["startups", params],
    queryFn: () => listStartups(params),
  });

  function applySearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setQuery(draftQuery.trim());
  }

  function updateFilter(setter: (value: string) => void, value: string) {
    setPage(1);
    setter(value);
  }

  const results = startupsQuery.data;
  const totalPages = results ? Math.max(1, Math.ceil(results.total / PAGE_SIZE)) : 1;

  return (
    <div className="mt-8 space-y-5">
      <form className="grid gap-3 rounded-xl border border-[var(--surface-border)] bg-[var(--surface)] p-4 md:grid-cols-5" onSubmit={applySearch}>
        <input aria-label="Buscar startups" className="rounded-md border border-[var(--surface-border)] bg-transparent px-3 py-2 md:col-span-2" onChange={(event) => setDraftQuery(event.target.value)} placeholder="Buscar nome ou descricao" value={draftQuery} />
        <input aria-label="Filtrar por setor" className="rounded-md border border-[var(--surface-border)] bg-transparent px-3 py-2" onChange={(event) => updateFilter(setSector, event.target.value)} placeholder="Setor" value={sector} />
        <input aria-label="Filtrar por pais" className="rounded-md border border-[var(--surface-border)] bg-transparent px-3 py-2" onChange={(event) => updateFilter(setCountry, event.target.value)} placeholder="Pais" value={country} />
        <div className="flex gap-2"><select aria-label="Filtrar por maturidade de IA" className="min-w-0 flex-1 rounded-md border border-[var(--surface-border)] bg-[var(--surface)] px-3 py-2" onChange={(event) => updateFilter(setMaturity, event.target.value)} value={maturity}><option value="">Maturidade IA</option><option value="ai_native">AI-native</option><option value="ai_enabled">AI-enabled</option><option value="non_ai">Nao IA</option></select><button className="rounded-md bg-[var(--accent)] px-3 font-semibold text-[#07111f]" type="submit">Buscar</button></div>
      </form>

      {startupsQuery.isLoading ? <p className="text-[var(--muted)]">Carregando portfolio...</p> : null}
      {startupsQuery.isError ? <p className="rounded-md border border-[var(--danger)] p-4 text-[var(--danger)]">{startupsQuery.error.message}</p> : null}
      {!startupsQuery.isLoading && !startupsQuery.isError && !results?.items.length ? <p className="rounded-xl border border-[var(--surface-border)] bg-[var(--surface)] p-6 text-[var(--muted)]">Nenhuma startup corresponde aos filtros atuais.</p> : null}

      {results?.items.length ? <>
        <p className="text-sm text-[var(--muted)]">{results.total} startup{results.total === 1 ? "" : "s"} analisada{results.total === 1 ? "" : "s"}</p>
        <div className="grid gap-4 md:grid-cols-2">
          {results.items.map((startup) => <Link className="rounded-xl border border-[var(--surface-border)] bg-[var(--surface)] p-5 transition hover:border-[var(--accent)]" href={`/startups/${startup.id}`} key={startup.id}><div className="flex items-start justify-between gap-3"><h2 className="text-xl font-semibold">{startup.name}</h2><span className="rounded-full bg-[#183414] px-2 py-1 text-xs font-semibold text-[var(--accent)]">{maturityLabel(startup.ai_maturity_level)}</span></div><p className="mt-3 line-clamp-3 text-sm leading-6 text-[var(--muted)]">{startup.description || "Perfil em enriquecimento."}</p><p className="mt-4 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{[startup.sector, startup.country].filter(Boolean).join(" · ") || "Setor e pais pendentes"}</p></Link>)}
        </div>
        {totalPages > 1 ? <nav aria-label="Paginacao do portfolio" className="flex items-center justify-between"><button className="rounded-md border border-[var(--surface-border)] px-3 py-2 disabled:opacity-50" disabled={page === 1} onClick={() => setPage((current) => current - 1)} type="button">Anterior</button><span className="text-sm text-[var(--muted)]">Pagina {page} de {totalPages}</span><button className="rounded-md border border-[var(--surface-border)] px-3 py-2 disabled:opacity-50" disabled={page === totalPages} onClick={() => setPage((current) => current + 1)} type="button">Proxima</button></nav> : null}
      </> : null}
    </div>
  );
}
