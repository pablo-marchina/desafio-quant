import { PortfolioCharts } from "@/features/dashboard/portfolio-charts";
import { StartupCompare } from "@/features/dashboard/startup-compare";
import { BatchSubmit } from "@/features/dashboard/batch-submit";

export const metadata = { title: "Dashboard — NVIDIA Startup AI Radar" };

export default function DashboardPage() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-10 flex flex-col gap-10">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-700">
          Visão geral do portfólio, comparação de startups e submissão em lote.
        </p>
      </div>

      <PortfolioCharts />

      <StartupCompare />

      <BatchSubmit />
    </main>
  );
}
