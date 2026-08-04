"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getStartup, listRecommendations, listStartups } from "@/lib/api/radar-client";
import type { Startup } from "@/lib/api/radar-types";

type CompareSlot = { startupId: string };

function maturityLabel(level: string | null) {
  if (!level) return "Sem classificacao";
  return { ai_native: "AI-Native", ai_enabled: "AI-Enabled", non_ai: "Non-AI" }[level] ?? level;
}

function maturityColor(level: string | null) {
  return {
    ai_native: "bg-green-100 text-green-800",
    ai_enabled: "bg-blue-100 text-blue-800",
    non_ai: "bg-gray-100 text-gray-600",
  }[level ?? ""] ?? "bg-gray-100 text-gray-700";
}

function StartupCard({ startupId }: CompareSlot) {
  const { data: startup, isLoading: loadingStartup } = useQuery({
    queryKey: ["startup", startupId],
    queryFn: () => getStartup(startupId),
    enabled: !!startupId,
  });

  const { data: recs, isLoading: loadingRecs } = useQuery({
    queryKey: ["recommendations", startupId],
    queryFn: () => listRecommendations(startupId),
    enabled: !!startupId,
  });

  if (loadingStartup || loadingRecs) {
    return <div className="p-4 text-gray-600 text-sm">Carregando...</div>;
  }
  if (!startup) {
    return <div className="p-4 text-red-400 text-sm">Startup nao encontrada.</div>;
  }

  const bestRec = recs ? [...recs].sort((a, b) => b.score - a.score)[0] : undefined;

  return (
    <div className="flex flex-col gap-3">
      <div>
        <h3 className="font-semibold text-gray-900 truncate">{startup.name}</h3>
        {startup.website_url && (
          <a
            href={startup.website_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-500 hover:underline truncate block"
          >
            {startup.website_url}
          </a>
        )}
      </div>

      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium w-fit ${maturityColor(startup.ai_maturity_level)}`}>
        {maturityLabel(startup.ai_maturity_level)}
      </span>

      {startup.sector && (
        <p className="text-xs text-gray-700">Setor: {startup.sector}</p>
      )}

      {bestRec ? (
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs font-medium text-gray-700 mb-1">Melhor recomendacao</p>
          <p className="text-sm font-semibold text-gray-800">{bestRec.technology_name}</p>
          <p className="text-xs text-gray-700">Score: {(bestRec.score * 100).toFixed(0)}%</p>
        </div>
      ) : (
        <p className="text-xs text-gray-600">Sem recomendacoes geradas.</p>
      )}

      <div>
        <p className="text-xs font-medium text-gray-700 mb-1">
          Recomendacoes ({recs?.length ?? 0})
        </p>
        <div className="flex flex-wrap gap-1">
          {recs?.slice(0, 5).map((r) => (
            <span
              key={r.id}
              className="text-xs bg-nvidia-green/10 text-green-800 rounded px-2 py-0.5"
            >
              {r.technology_name}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function CompareSelect({
  index,
  value,
  startups,
  selectedIds,
  isLoading,
  onChange,
}: {
  index: number;
  value: string;
  startups: Startup[];
  selectedIds: string[];
  isLoading: boolean;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-gray-700">
        Startup {index + 1}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-gray-400 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-green-600"
        disabled={isLoading}
        aria-label={`Selecionar startup ${index + 1}`}
      >
        <option value="">{isLoading ? "Carregando startups..." : "Selecione uma startup"}</option>
        {startups.map((startup) => {
          const alreadySelected = selectedIds.includes(startup.id) && startup.id !== value;
          const detail = [startup.sector, startup.country].filter(Boolean).join(" - ");
          return (
            <option key={startup.id} value={startup.id} disabled={alreadySelected}>
              {startup.name}{detail ? ` (${detail})` : ""}
            </option>
          );
        })}
      </select>
    </div>
  );
}

export function StartupCompare() {
  const [ids, setIds] = useState(["", "", ""]);
  const activeIds = ids.filter((id) => id.trim().length > 0);
  const selectedIds = ids.filter(Boolean);
  const { data: startupPage, isLoading } = useQuery({
    queryKey: ["startups", "compare-options"],
    queryFn: () => listStartups({ page: 1, page_size: 100 }),
  });
  const startups = startupPage?.items ?? [];

  const update = (i: number, v: string) =>
    setIds((prev) => prev.map((old, idx) => (idx === i ? v : old)));

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
      <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">
        Comparacao de Startups
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {ids.map((id, i) => (
          <CompareSelect
            key={i}
            index={i}
            value={id}
            startups={startups}
            selectedIds={selectedIds}
            isLoading={isLoading}
            onChange={(v) => update(i, v)}
          />
        ))}
      </div>

      {activeIds.length === 0 ? (
        <p className="text-sm text-gray-600 text-center py-8">
          Selecione startups acima para comparar lado a lado.
        </p>
      ) : (
        <div
          className="grid gap-6"
          style={{ gridTemplateColumns: `repeat(${activeIds.length}, minmax(0, 1fr))` }}
        >
          {activeIds.map((id) => (
            <div key={id} className="border border-gray-100 rounded-lg p-4">
              <StartupCard startupId={id} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
