"use client";

import { Github } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { DashboardSummary } from "@/lib/types";
import { formatNumber } from "@/lib/utils";

const dateFormatter = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  timeZone: "America/Bahia"
});

const fullDateFormatter = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "full",
  timeZone: "America/Bahia"
});

function localDate(date: string) {
  return new Date(`${date}T12:00:00-03:00`);
}

export function AutomationRegistrationsChart({
  summary,
  loading
}: {
  summary?: DashboardSummary;
  loading: boolean;
}) {
  const data = (summary?.github_actions_registrations || []).map((point) => ({
    ...point,
    label: `${point.weekday} ${dateFormatter.format(localDate(point.date))}`
  }));
  const periodTotal = data.reduce((total, point) => total + point.count, 0);

  return (
    <Card className="p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Github className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-sm font-semibold">
              Startups registradas pela automação
            </h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Execuções do GitHub Actions às segundas e quintas
          </p>
        </div>
        <div className="mt-2 sm:mt-0 sm:text-right">
          <p className="text-xl font-semibold leading-none">
            {loading ? "—" : formatNumber(periodTotal)}
          </p>
          <p className="mt-1 text-[10px] uppercase tracking-wide text-muted-foreground">
            últimas 8 execuções
          </p>
        </div>
      </div>
      {loading ? (
        <Skeleton className="mt-4 h-[118px] w-full" />
      ) : (
        <div
          className="mt-3 h-[118px] w-full"
          role="img"
          aria-label="Quantidade de startups registradas nas últimas oito execuções de segunda e quinta"
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={data}
              margin={{ top: 8, right: 12, bottom: 0, left: -24 }}
            >
              <CartesianGrid
                stroke="rgba(255,255,255,.05)"
                strokeDasharray="3 3"
                vertical={false}
              />
              <XAxis
                dataKey="label"
                tick={{ fill: "#7f8a96", fontSize: 10 }}
                axisLine={{ stroke: "rgba(255,255,255,.08)" }}
                tickLine={false}
                interval={0}
              />
              <YAxis
                allowDecimals={false}
                domain={[0, "dataMax + 1"]}
                tick={{ fill: "#7f8a96", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ stroke: "rgba(118,185,0,.3)", strokeWidth: 1 }}
                contentStyle={{
                  background: "#111820",
                  border: "1px solid rgba(255,255,255,.08)",
                  borderRadius: 8,
                  fontSize: 12
                }}
                labelFormatter={(_, payload) =>
                  payload?.[0]
                    ? fullDateFormatter.format(
                        localDate(String(payload[0].payload.date))
                      )
                    : ""
                }
                formatter={(value: number) => [
                  formatNumber(value),
                  "Startups registradas"
                ]}
              />
              <Line
                type="monotone"
                dataKey="count"
                stroke="#76b900"
                strokeWidth={2}
                dot={{
                  r: 3.5,
                  fill: "#0c1117",
                  stroke: "#76b900",
                  strokeWidth: 2
                }}
                activeDot={{ r: 5, fill: "#76b900", strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}
