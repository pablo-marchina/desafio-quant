import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useMemo, useState, useCallback } from "react";
import { Search, Sparkles, BarChart3, FileSearch, FileText, TrendingUp, ShieldCheck, Cpu, Database, ArrowRight, Handshake, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScoreBar, MaturityBadge, SectionTitle, CompanyLogo, ContactStatusBadge } from "@/components/ui-bits";
import { useContacts } from "@/lib/contacts-store";
import { useHealth } from "@/lib/hooks/use-health";
import { useStartups } from "@/lib/hooks/use-startups";
import { useRuns } from "@/lib/hooks/use-runs";
import { useQueryClient } from "@tanstack/react-query";
import { ApiErrorDisplay } from "@/components/api-error-display";
import { PipelineDialog } from "@/components/pipeline-dialog";
import type { StartupRecord } from "@/lib/api";
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  AreaChart, Area,
} from "recharts";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Overview — NVIDIA Toph" },
      { name: "description", content: "Visão geral do radar de startups brasileiras AI-native." },
    ],
  }),
  component: Overview,
});

const DONUT_COLORS = ["var(--color-primary)", "var(--color-info)", "#94a3b8"];

function Metric({ label, value, hint, icon: Icon }: { label: string; value: string | number; hint?: string; icon: any }) {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">{value}</p>
          {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
        </div>
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
          <Icon className="h-4 w-4" />
        </div>
      </div>
    </Card>
  );
}

function Overview() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [dialogQuery, setDialogQuery] = useState<string | null>(null);
  const contacts = useContacts();
  const { data: health, error: healthError, refetch: retryHealth } = useHealth();
  const { data: startupRecords = [], isLoading: startupsLoading, error: startupsError } = useStartups();
  const { data: runs = [] } = useRuns();
  const apiOk = health?.status === "ok";

  const {
    metrics,
    maturityData,
    sectorData,
    top,
  } = useMemo(() => {
    const records = startupRecords as StartupRecord[];
    const aiNative = records.filter((s) => s.classification_label === "AI-Native").length;
    const aiEnabled = records.filter((s) => s.classification_label === "AI-Enabled").length;
    const nonAi = records.filter((s) => s.classification_label === "Non-AI").length;
    const totalEvidence = records.reduce((acc, s) => acc + ((s as any).evidence_count ?? 0), 0);
    const totalRecommendations = records.reduce((acc, s) => acc + ((s as any).recommendation_count ?? 0), 0);

    return {
      metrics: {
        analyzed: records.length,
        aiNative,
        validatedEvidences: totalEvidence,
        recommendations: totalRecommendations,
        briefings: runs.filter((r) => r.status === "completed").length,
      },
      maturityData: [
        { name: "AI-Native", value: aiNative || 0 },
        { name: "AI-Enabled", value: aiEnabled || 0 },
        { name: "Non-AI", value: nonAi || 0 },
      ].filter((d) => d.value > 0),
      sectorData: Object.entries(
        records.reduce<Record<string, number>>((acc, s) => {
          const key = s.sector || "Não informado";
          acc[key] = (acc[key] ?? 0) + 1;
          return acc;
        }, {}),
      )
        .map(([name, value]) => ({ name, value }))
        .sort((a, b) => b.value - a.value),
      top: [...records]
        .sort((a, b) => ((b as any).radar_score ?? 0) - ((a as any).radar_score ?? 0))
        .slice(0, 4),
    };
  }, [startupRecords, runs]);

  const onAnalyze = () => {
    const query = q.trim();
    if (query) setDialogQuery(query);
  };

  const handlePipelineComplete = useCallback(() => {
    setDialogQuery(null);
    qc.invalidateQueries({ queryKey: ["startups"] });
    qc.invalidateQueries({ queryKey: ["runs"] });
  }, [qc]);

  const error = healthError ?? startupsError;
  if (error && !apiOk) {
    return (
      <div className="mx-auto w-full max-w-7xl space-y-5 p-4 md:p-6">
        <ApiErrorDisplay
          error={error as any}
          onRetry={() => retryHealth()}
        />
      </div>
    );
  }

  if (!health || startupsLoading) {
    return (
      <div className="mx-auto w-full max-w-7xl space-y-6 p-4 md:p-6">
        <Card className="p-4 md:p-6">
          <div className="space-y-3">
            <Skeleton className="h-6 w-64" />
            <Skeleton className="h-11 w-full" />
          </div>
        </Card>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          {[1,2,3,4,5].map((i) => <Skeleton key={i} className="h-24" />)}
        </div>
        <div className="grid gap-4 lg:grid-cols-6">
          <Skeleton className="h-72 lg:col-span-2" />
          <Skeleton className="h-72 lg:col-span-2" />
          <Skeleton className="h-72 lg:col-span-2" />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 p-4 md:p-6">
      {/* Search hero */}
      <Card className="border-border p-4 md:p-6">
        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 sm:flex sm:flex-wrap sm:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="truncate text-base font-semibold text-foreground md:text-lg">Radar de startups brasileiras AI-native</h1>
              <Badge variant="outline" className={`gap-1 text-[10px] ${apiOk ? "border-green-500/30 bg-green-500/5 text-green-600" : "border-primary/30 bg-primary/5 text-primary"}`}>
                {apiOk ? <><CheckCircle2 className="h-3 w-3" /> API ativa</> : <><Database className="h-3 w-3" /> Demo data</>}
              </Badge>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">Apenas dados públicos. Toda recomendação NVIDIA é justificada e rastreável até a fonte.</p>
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && onAnalyze()}
              placeholder="Pesquisar startup por nome"
              className="h-11 pl-9 text-sm"
            />
          </div>
          <Button size="lg" className="h-11 gap-1.5" onClick={onAnalyze}>
            <Sparkles className="h-4 w-4" /> Analisar empresa
          </Button>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <Button variant="outline" size="sm" className="gap-1.5" onClick={() => navigate({ to: "/ranking" })}>
            <BarChart3 className="h-3.5 w-3.5" /> Ver ranking geral
          </Button>
          <Button variant="outline" size="sm" className="gap-1.5" onClick={() => navigate({ to: "/contacts" })}>
            <Handshake className="h-3.5 w-3.5" /> Contatos comerciais
          </Button>
          <Button variant="outline" size="sm" className="gap-1.5" onClick={() => navigate({ to: "/sources" })}>
            <FileSearch className="h-3.5 w-3.5" /> Explorar fontes
          </Button>
          <Button variant="outline" size="sm" className="gap-1.5" onClick={() => navigate({ to: "/briefing" })}>
            <FileText className="h-3.5 w-3.5" /> Gerar briefing
          </Button>
        </div>
      </Card>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Metric label="Startups analisadas" value={metrics.analyzed} hint="na base" icon={Cpu} />
        <Metric label="AI-Native candidates" value={metrics.aiNative} hint="classificadas" icon={Sparkles} />
        <Metric label="Evidências" value={metrics.validatedEvidences} hint="coletadas" icon={ShieldCheck} />
        <Metric label="Recomendações NVIDIA" value={metrics.recommendations} hint="geradas" icon={TrendingUp} />
        <Metric label="Execuções" value={metrics.briefings} hint="pipelines completos" icon={FileText} />
      </div>

      {/* Donut + sector + region */}
      <div className="grid gap-4 lg:grid-cols-6">
        <Card className="p-4 lg:col-span-2">
          <SectionTitle title="Maturidade de IA" desc={`${metrics.analyzed} startups classificadas`} />
          <div className="h-60 w-full">
            {maturityData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={maturityData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={55}
                    outerRadius={85}
                    paddingAngle={2}
                    stroke="var(--color-background)"
                    strokeWidth={2}
                  >
                    {maturityData.map((_, i) => <Cell key={i} fill={DONUT_COLORS[i % DONUT_COLORS.length]} />)}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 6, fontSize: 12 }}
                  />
                  <Legend verticalAlign="bottom" iconType="circle" wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-muted-foreground">Nenhuma startup classificada</div>
            )}
          </div>
        </Card>

        <Card className="p-4 lg:col-span-2">
          <SectionTitle title="Distribuição por setor" desc="Setores na base" />
          <div className="h-60 w-full">
            {sectorData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={sectorData} layout="vertical" margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                  <CartesianGrid horizontal={false} stroke="var(--color-border)" />
                  <XAxis type="number" tickLine={false} axisLine={false} fontSize={10} stroke="var(--color-muted-foreground)" />
                  <YAxis type="category" dataKey="name" tickLine={false} axisLine={false} fontSize={11} width={90} stroke="var(--color-muted-foreground)" />
                  <Tooltip
                    contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 6, fontSize: 12 }}
                    cursor={{ fill: "var(--color-muted)" }}
                  />
                  <Bar dataKey="value" fill="var(--color-primary)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-muted-foreground">Nenhum setor registrado</div>
            )}
          </div>
        </Card>

        <Card className="p-4 lg:col-span-2">
          <SectionTitle title="Atividade" desc="Execuções recentes do pipeline" />
          <div className="h-60 w-full">
            {runs.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={runs.slice(0, 10).map((r) => ({
                  name: `#${r.id}`,
                  value: 1,
                }))} margin={{ top: 8, right: 8, bottom: 8, left: -16 }}>
                  <CartesianGrid vertical={false} stroke="var(--color-border)" />
                  <XAxis dataKey="name" tickLine={false} axisLine={false} fontSize={11} stroke="var(--color-muted-foreground)" />
                  <YAxis hide />
                  <Tooltip
                    contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 6, fontSize: 12 }}
                    cursor={{ fill: "var(--color-muted)" }}
                    formatter={() => ["1 execução", ""]}
                  />
                  <Bar dataKey="value" fill="var(--color-info)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-muted-foreground">Nenhuma execução ainda</div>
            )}
          </div>
        </Card>
      </div>

      {/* Pipeline dialog */}
      {dialogQuery && (
        <PipelineDialog
          query={dialogQuery}
          open={dialogQuery !== null}
          onOpenChange={() => setDialogQuery(null)}
          onComplete={handlePipelineComplete}
        />
      )}

      {/* Top opportunities */}
      <Card className="p-4">
        <SectionTitle
          title="Top opportunities"
          desc="Startups com maior Radar score"
          right={
            <Button variant="ghost" size="sm" className="gap-1 text-xs" onClick={() => navigate({ to: "/ranking" })}>
              Ver ranking <ArrowRight className="h-3 w-3" />
            </Button>
          }
        />
        <div className="divide-y divide-border">
          {top.map((s) => {
            const status = contacts[s.id]?.status;
            return (
              <Link
                key={s.id}
                to="/startup/$id"
                params={{ id: s.id }}
                className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 py-3 transition hover:bg-muted/40 sm:grid-cols-[auto_minmax(0,2fr)_minmax(0,1.5fr)_auto]"
              >
                <CompanyLogo id={s.id} name={s.name} size="md" />
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate text-sm font-medium text-foreground">{s.name}</span>
                    {s.classification_label && <MaturityBadge value={s.classification_label as any} />}
                    {status && status !== "Não contactada" && <ContactStatusBadge status={status} />}
                  </div>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">{s.sector || "—"}</p>
                </div>
                <div className="hidden min-w-0 sm:block">
                  <ScoreBar value={(s as any).radar_score ?? 0} />
                  <p className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">Radar score</p>
                </div>
                <Button variant="ghost" size="sm" className="gap-1 text-xs">
                  Ver <ArrowRight className="h-3 w-3" />
                </Button>
              </Link>
            );
          })}
          {top.length === 0 && (
            <p className="py-6 text-center text-xs text-muted-foreground">Nenhuma startup encontrada. Execute o pipeline primeiro.</p>
          )}
        </div>
      </Card>
    </div>
  );
}
