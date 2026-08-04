"use client";

import { useState } from "react";
import { createBatchUrlIngestionJobs } from "@/lib/api/radar-client";
import type { UrlIngestionJob } from "@/lib/api/radar-types";

type BatchResult = {
  url: string;
  job: UrlIngestionJob | null;
  error: string | null;
};

function parseUrls(raw: string): string[] {
  return raw
    .split(/[\n,]+/)
    .map((u) => u.trim())
    .filter((u) => u.startsWith("http"));
}

export function BatchSubmit() {
  const [raw, setRaw] = useState("");
  const [results, setResults] = useState<BatchResult[]>([]);
  const [loading, setLoading] = useState(false);

  const urls = parseUrls(raw);

  async function handleSubmit() {
    if (urls.length === 0) return;
    setLoading(true);
    try {
      const res = await createBatchUrlIngestionJobs(urls);
      setResults(res);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
      <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">
        Fila de Análise em Lote
      </h2>
      <p className="text-xs text-gray-600 mb-3">
        Cole as URLs das startups separadas por linha ou vírgula. Cada URL gera um job de análise
        independente.
      </p>

      <textarea
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
        rows={5}
        placeholder={`https://startup1.com.br\nhttps://startup2.io\nhttps://startup3.com`}
        className="w-full rounded-lg border border-gray-400 px-3 py-2 text-sm font-mono text-gray-900 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-green-600 mb-3"
      />

      <div className="flex items-center gap-3 mb-4">
        <button
          onClick={handleSubmit}
          disabled={loading || urls.length === 0}
          className="px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Enviando..." : `Analisar ${urls.length} URL${urls.length !== 1 ? "s" : ""}`}
        </button>
        {urls.length > 0 && !loading && (
          <span className="text-xs text-gray-600">{urls.length} URL{urls.length !== 1 ? "s" : ""} detectada{urls.length !== 1 ? "s" : ""}</span>
        )}
      </div>

      {results.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-gray-700 mb-2">Resultados:</p>
          {results.map((r, i) => (
            <div
              key={i}
              className={`flex items-start justify-between gap-2 rounded-lg px-3 py-2 text-xs ${
                r.error ? "bg-red-50 text-red-700" : "bg-green-50 text-green-800"
              }`}
            >
              <span className="truncate flex-1">{r.url}</span>
              {r.job ? (
                <a
                  href={`/jobs/${r.job.id}`}
                  className="whitespace-nowrap underline hover:no-underline"
                >
                  Ver job →
                </a>
              ) : (
                <span className="whitespace-nowrap">{r.error ?? "Erro desconhecido"}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
