"use client";

import { useQuery } from "@tanstack/react-query";
import { getPortfolioStats, getTechnologyStats } from "@/lib/api/radar-client";

const MATURITY_COLORS = {
  "AI-Native": "#76b900",
  "AI-Enabled": "#3b82f6",
  "Non-AI": "#6b7280",
  "Sem classificação": "#d1d5db",
} as const;

type MaturityKey = keyof typeof MATURITY_COLORS;

function PieSlice({
  cx, cy, r, startAngle, endAngle, fill,
}: {
  cx: number; cy: number; r: number;
  startAngle: number; endAngle: number; fill: string;
}) {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const x1 = cx + r * Math.cos(toRad(startAngle));
  const y1 = cy + r * Math.sin(toRad(startAngle));
  const x2 = cx + r * Math.cos(toRad(endAngle));
  const y2 = cy + r * Math.sin(toRad(endAngle));
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return (
    <path
      d={`M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`}
      fill={fill}
    />
  );
}

function MaturityPieChart() {
  const { data, isLoading } = useQuery({
    queryKey: ["portfolio-stats"],
    queryFn: getPortfolioStats,
  });

  if (isLoading || !data) {
    return <div className="h-64 flex items-center justify-center text-gray-600 text-sm">Carregando...</div>;
  }

  const slices: { name: MaturityKey; value: number }[] = [
    { name: "AI-Native", value: data.ai_native },
    { name: "AI-Enabled", value: data.ai_enabled },
    { name: "Non-AI", value: data.non_ai },
    { name: "Sem classificação", value: data.unclassified },
  ].filter((s) => s.value > 0) as { name: MaturityKey; value: number }[];

  if (slices.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-600 text-sm">
        Nenhuma startup classificada ainda.
      </div>
    );
  }

  const total = slices.reduce((s, d) => s + d.value, 0);
  let angle = -90;
  const rendered = slices.map((s) => {
    const sweep = (s.value / total) * 360;
    const start = angle;
    angle += sweep;
    return { ...s, start, end: angle, sweep };
  });

  return (
    <div data-testid="maturity-pie">
      <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-1">
        Distribuição por Maturidade em IA
      </h2>
      <p className="text-xs text-gray-600 mb-4">Total: {total} startup{total !== 1 ? "s" : ""}</p>
      <div className="flex items-center gap-6">
        <svg viewBox="0 0 160 160" className="w-40 h-40 flex-shrink-0" aria-hidden>
          {rendered.map((s) => (
            <PieSlice
              key={s.name}
              cx={80} cy={80} r={70}
              startAngle={s.start} endAngle={s.end}
              fill={MATURITY_COLORS[s.name]}
            />
          ))}
        </svg>
        <ul className="flex flex-col gap-2 text-xs">
          {rendered.map((s) => (
            <li key={s.name} className="flex items-center gap-2">
              <span
                className="inline-block w-3 h-3 rounded-sm flex-shrink-0"
                style={{ background: MATURITY_COLORS[s.name] }}
              />
              <span className="text-gray-800">{s.name}</span>
              <span className="font-semibold text-gray-900">{s.value}</span>
              <span className="text-gray-600">({((s.value / total) * 100).toFixed(0)}%)</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function TechnologyBarChart() {
  const { data, isLoading } = useQuery({
    queryKey: ["technology-stats"],
    queryFn: () => getTechnologyStats(10),
  });

  if (isLoading || !data) {
    return <div className="h-64 flex items-center justify-center text-gray-600 text-sm">Carregando...</div>;
  }

  if (data.items.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-600 text-sm">
        Nenhuma recomendação gerada ainda.
      </div>
    );
  }

  const max = Math.max(...data.items.map((d) => d.count));

  return (
    <div data-testid="tech-bar">
      <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-1">
        Tecnologias NVIDIA Mais Recomendadas
      </h2>
      <p className="text-xs text-gray-600 mb-4">Top {data.items.length} por número de startups</p>
      <ol className="flex flex-col gap-2">
        {data.items.map((item) => (
          <li key={item.technology_slug} className="flex items-center gap-2 text-xs">
            <span className="w-36 truncate text-right text-gray-800 flex-shrink-0">
              {item.technology_name}
            </span>
            <div className="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden">
              <div
                className="h-3 rounded-full"
                style={{
                  width: `${(item.count / max) * 100}%`,
                  background: "#76b900",
                }}
              />
            </div>
            <span className="font-semibold text-gray-900 w-4 text-right">{item.count}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function PortfolioCharts() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
        <MaturityPieChart />
      </div>
      <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
        <TechnologyBarChart />
      </div>
    </div>
  );
}
