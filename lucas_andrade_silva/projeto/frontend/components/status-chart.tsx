"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { Card } from "@/components/ui/card";
import { InsufficientData } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";
import { normalizeAiClassification } from "@/lib/status";
import type { DashboardSummary } from "@/lib/types";

const categories = [
  { key: "AI_NATIVE", name: "AI Native", color: "#76b900" },
  { key: "AI_ENABLED", name: "AI Enabled", color: "#a3d65c" },
  { key: "NON_AI", name: "Non-AI", color: "#64748b" }
] as const;

export function StatusChart({
  summary,
  loading
}: {
  summary?: DashboardSummary;
  loading: boolean;
}) {
  const classifications = summary?.ai_classifications || {};
  const grouped = Object.entries(classifications).reduce(
    (acc, [name, value]) => {
      const normalized = normalizeAiClassification(name);
      const key =
        normalized === "AI_NATIVE" || normalized === "AI_ENABLED"
          ? normalized
          : "NON_AI";
      acc[key] = (acc[key] || 0) + value;
      return acc;
    },
    { AI_NATIVE: 0, AI_ENABLED: 0, NON_AI: 0 } as Record<string, number>
  );
  const data = categories.map((category) => ({
    ...category,
    value: grouped[category.key]
  }));
  const hasData = Object.values(classifications).some((value) => value > 0);

  return (
    <Card className="p-4">
      <div>
        <h2 className="text-sm font-semibold">
          Distribuição por classificação de IA
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Quantidade atual por dependência de inteligência artificial
        </p>
      </div>
      {loading ? (
        <Skeleton className="mt-5 h-[230px] w-full" />
      ) : !hasData ? (
        <InsufficientData message="A API ainda não retornou classificações suficientes para gerar o gráfico." />
      ) : (
        <div className="mt-4 h-[230px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ left: -15, right: 8 }}>
              <CartesianGrid stroke="rgba(255,255,255,.05)" vertical={false} />
              <XAxis
                dataKey="name"
                tick={{ fill: "#7f8a96", fontSize: 10 }}
                axisLine={{ stroke: "rgba(255,255,255,.08)" }}
                tickLine={false}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fill: "#7f8a96", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: "rgba(255,255,255,.025)" }}
                contentStyle={{
                  background: "#111820",
                  border: "1px solid rgba(255,255,255,.08)",
                  borderRadius: 8,
                  color: "#f8fafc",
                  fontSize: 12
                }}
                itemStyle={{ color: "#f8fafc" }}
                labelStyle={{ color: "#f8fafc" }}
                formatter={(value: number) => [value, "Startups"]}
              />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {data.map((entry) => (
                  <Cell key={entry.key} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}
