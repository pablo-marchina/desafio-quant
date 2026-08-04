import { useState } from 'react'
import { Activity, CheckCircle2, Clock, Plus, Rocket } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { MetricKPI } from '@/components/ui/MetricKPI'
import { GlassPanel } from '@/components/ui/GlassPanel'
import { StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { MaturityDistribution } from '@/components/charts/MaturityDistribution'
import { Spinner } from '@/components/ui/Spinner'
import { useMetrics } from '@/hooks/useMetrics'
import { useStartups } from '@/hooks/useStartups'
import { useCreateBatch } from '@/hooks/useBatches'
import { runBatch } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'

export default function Dashboard() {
  const { metrics, loading, error, refetch } = useMetrics(30_000)
  const { startups } = useStartups(100)
  const { create, loading: creating, error: createError } = useCreateBatch()
  const navigate = useNavigate()
  const role = useAuthStore((state) => state.role)
  const [showAnalysis, setShowAnalysis] = useState(false)
  const [startupId, setStartupId] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)
  const canAnalyze = role === 'admin' || role === 'analyst'

  if (loading) return <div className="empty-state"><Spinner size="lg" /><p>Carregando dashboard...</p></div>
  if (error) return <div className="empty-state"><p className="text-error">Nao foi possivel carregar o dashboard: {error}</p><Button onClick={refetch}>Tentar novamente</Button></div>

  const recent = [...startups]
    .filter((startup) => startup.pipeline_runs?.[0])
    .sort((a, b) => String(b.pipeline_runs?.[0]?.created_at).localeCompare(String(a.pipeline_runs?.[0]?.created_at)))
    .slice(0, 6)

  const startAnalysis = async () => {
    const startup = startups.find((item) => item.id === startupId)
    if (!startup?.external_id) {
      setActionError('Selecione uma startup valida.')
      return
    }
    setActionError(null)
    const batch = await create({ startup_ids: [startup.external_id], limit: 1, max_attempts: 2 })
    if (!batch) return
    try {
      await runBatch(batch.id)
      navigate(`/batches/${batch.id}`)
    } catch (requestError) {
      setActionError(requestError instanceof Error ? requestError.message : 'Nao foi possivel iniciar a analise.')
    }
  }

  const kpis = [
    { label: 'Startups mapeadas', value: metrics?.total_startups ?? 0, icon: <Rocket size={18} /> },
    { label: 'Execucoes hoje', value: metrics?.runs_today ?? 0, icon: <Activity size={18} /> },
    { label: 'Conclusao historica', value: metrics?.success_rate ?? 0, format: 'percent' as const, icon: <CheckCircle2 size={18} /> },
    { label: 'Duracao media concluida', value: metrics?.avg_duration_ms ?? 0, format: 'duration' as const, icon: <Clock size={18} /> },
  ]

  return <div>
    <div className="grid grid-4" style={{ gap: '1rem', marginBottom: '1.5rem' }}>{kpis.map((kpi) => <MetricKPI key={kpi.label} {...kpi} />)}</div>

    <div className="dashboard-main-grid">
      <GlassPanel><h2 style={{ fontSize: '1rem', marginBottom: '1rem' }}>Distribuicao por classificacao de IA</h2><MaturityDistribution data={metrics?.maturity_distribution ?? {}} /></GlassPanel>
      <GlassPanel>
        <div className="flex items-center justify-between gap-2 mb-4"><div><h2 style={{ fontSize: '1rem' }}>Analises mais recentes</h2><p className="text-xs text-muted mt-1">Ultima execucao de cada startup</p></div>{canAnalyze && <Button size="sm" icon={<Plus size={14} />} onClick={() => setShowAnalysis(true)}>Nova analise</Button>}</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>{recent.map((startup) => { const run = startup.pipeline_runs?.[0]; return <button className="analysis-row" key={startup.id} onClick={() => navigate(`/startups/${startup.id}`)}><span><strong>{startup.nome}</strong><small>{startup.maturity_class ?? 'Nao classificada'}</small></span>{run && <StatusBadge status={run.status} />}</button> })}</div>
      </GlassPanel>
    </div>

    <GlassPanel><h2 style={{ fontSize: '1rem', marginBottom: '1rem' }}>Resumo historico de execucoes</h2><div className="grid grid-4" style={{ gap: '1rem' }}>{[
      ['Total', metrics?.total_runs ?? 0], ['Concluidas', metrics?.completed_runs ?? 0], ['Parciais', metrics?.partial_runs ?? 0], ['Falhas', metrics?.failed_runs ?? 0],
    ].map(([label, value]) => <div key={String(label)} style={{ textAlign: 'center' }}><strong style={{ fontSize: '1.75rem' }}>{value}</strong><p className="text-xs text-muted">{label}</p></div>)}</div></GlassPanel>

    {showAnalysis && <div className="overlay" onClick={() => setShowAnalysis(false)}><div className="modal" onClick={(event) => event.stopPropagation()}><h2 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Nova analise</h2><label htmlFor="analysis-startup">Startup</label><select id="analysis-startup" className="input" value={startupId} onChange={(event) => setStartupId(event.target.value)}><option value="">Selecione...</option>{startups.filter((item) => item.external_id).map((item) => <option key={item.id} value={item.id}>{item.nome} - {item.site_oficial}</option>)}</select><p className="text-xs text-muted mt-2">A URL oficial cadastrada sera usada pelo pipeline de investigacao.</p>{(actionError || createError) && <p className="text-error text-sm mt-3">{actionError || createError}</p>}<div className="flex justify-between gap-2 mt-4"><Button variant="ghost" onClick={() => setShowAnalysis(false)}>Cancelar</Button><Button onClick={startAnalysis} loading={creating}>Criar e executar</Button></div></div></div>}
  </div>
}
