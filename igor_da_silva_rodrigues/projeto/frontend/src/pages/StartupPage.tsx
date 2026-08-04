import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import {
  ArrowLeft,
  Copy,
  Download,
  ExternalLink,
  Globe,
  MapPin,
  Printer,
  Tag,
} from 'lucide-react'
import { GlassPanel } from '@/components/ui/GlassPanel'
import { MaturityBadge, StatusBadge } from '@/components/ui/Badge'
import { ProgressRing } from '@/components/ui/ProgressRing'
import { Spinner } from '@/components/ui/Spinner'
import { Button } from '@/components/ui/Button'
import { PipelineTimeline } from '@/components/pipeline/PipelineTimeline'
import { useStartup } from '@/hooks/useStartups'
import { getPOCBlueprint, getRunAnalysis, getRunEvidences } from '@/lib/api'
import type { Evidence, POCBlueprint, RunAnalysis } from '@/types/api'

type TabId = 'diagnosis' | 'evidences' | 'recommendations' | 'poc' | 'impact' | 'briefing' | 'history'

const TABS: { id: TabId; label: string }[] = [
  { id: 'diagnosis', label: 'Diagnostico de IA' },
  { id: 'evidences', label: 'Evidencias' },
  { id: 'recommendations', label: 'Recomendacao NVIDIA' },
  { id: 'poc', label: 'POC Blueprint' },
  { id: 'impact', label: 'Impacto' },
  { id: 'briefing', label: 'Briefing' },
  { id: 'history', label: 'Historico' },
]

const MATURITY_LABELS: Record<number, string> = {
  0: 'Nao demonstrado',
  1: 'Experimental',
  2: 'Adocao inicial',
  3: 'Integracao',
  4: 'Avancado',
  5: 'Otimizado',
}

const HORIZON_LABELS: Record<string, string> = {
  curto_prazo: 'Curto prazo',
  medio_prazo: 'Medio prazo',
  longo_prazo: 'Longo prazo',
}

export default function StartupPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { startup, loading, error } = useStartup(id)
  const [activeTab, setActiveTab] = useState<TabId>('diagnosis')
  const [analysis, setAnalysis] = useState<RunAnalysis | null>(null)
  const [evidences, setEvidences] = useState<Evidence[]>([])
  const [pocBlueprint, setPOCBlueprint] = useState<POCBlueprint | null>(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [evidenceFilter, setEvidenceFilter] = useState('all')
  const [copyFeedback, setCopyFeedback] = useState('')
  const latestRun = startup?.pipeline_runs?.[0]

  const loadAnalysis = useCallback(async () => {
    if (!latestRun?.id) return
    setAnalysisLoading(true)
    setAnalysisError(null)
    try {
      const [analysisData, evidenceData, pocData] = await Promise.all([
        getRunAnalysis(latestRun.id),
        getRunEvidences(latestRun.id),
        getPOCBlueprint(latestRun.id).catch(() => null),
      ])
      setAnalysis(analysisData)
      setEvidences(evidenceData)
      setPOCBlueprint(pocData)
    } catch (requestError) {
      setAnalysisError(requestError instanceof Error ? requestError.message : 'Falha ao carregar analise')
    } finally {
      setAnalysisLoading(false)
    }
  }, [latestRun?.id])

  useEffect(() => { void loadAnalysis() }, [loadAnalysis])

  const visibleEvidences = useMemo(
    () => evidences.filter((item) => evidenceFilter === 'all' || item.classificacao === evidenceFilter),
    [evidences, evidenceFilter],
  )

  if (loading) return <div className="empty-state"><Spinner size="lg" /><p>Carregando startup...</p></div>
  if (error || !startup) return <div className="empty-state"><p className="text-error">{error ?? 'Startup nao encontrada'}</p><Button onClick={() => navigate('/startups')}>Voltar</Button></div>

  const assessment = analysis?.assessment
  const recommendation = analysis?.recommendation
  const refinement = analysis?.refinement
  const briefing = analysis?.briefing
  const maturityLevel = assessment?.maturity_level ?? 0
  const fitScore = refinement?.fit_score ?? ((recommendation?.opportunity_score ?? 0) / 10)

  const copyBriefing = async () => {
    if (!briefing?.markdown) return
    await navigator.clipboard.writeText(briefing.markdown)
    setCopyFeedback('Copiado')
    window.setTimeout(() => setCopyFeedback(''), 2_000)
  }

  const downloadBriefing = () => {
    if (!briefing?.markdown) return
    const blob = new Blob([briefing.markdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${startup.nome.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-briefing.md`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <Button variant="ghost" icon={<ArrowLeft size={15} />} onClick={() => navigate('/startups')} style={{ marginBottom: '1rem' }}>Startups</Button>

      <GlassPanel style={{ marginBottom: '1rem' }}>
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <h1 style={{ fontSize: '1.6rem', marginBottom: '0.5rem' }}>{startup.nome}</h1>
            <div className="flex flex-wrap gap-3 text-sm text-muted">
              {startup.categoria && <span className="flex items-center gap-1"><Tag size={13} />{startup.categoria}</span>}
              {(startup.cidade || startup.estado) && <span className="flex items-center gap-1"><MapPin size={13} />{[startup.cidade, startup.estado].filter(Boolean).join(', ')}</span>}
              {startup.pais && <span className="flex items-center gap-1"><Globe size={13} />{startup.pais}</span>}
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {assessment?.maturity_class && <MaturityBadge maturity={assessment.maturity_class} />}
            {latestRun && <StatusBadge status={latestRun.status} />}
            {startup.site_oficial && <a className="btn btn-secondary btn-sm" href={startup.site_oficial} target="_blank" rel="noopener noreferrer"><ExternalLink size={13} />Site oficial</a>}
          </div>
        </div>
      </GlassPanel>

      {latestRun && !analysisLoading && !analysisError && (
        <div className="grid grid-3" style={{ gap: '1rem', marginBottom: '1rem' }}>
          <GlassPanel><p className="text-xs text-muted">Nivel de maturidade</p><h2 style={{ marginTop: '0.4rem' }}>{maturityLevel}/5</h2><p className="text-sm text-muted">{MATURITY_LABELS[maturityLevel] ?? 'Nao informado'}</p></GlassPanel>
          <GlassPanel><p className="text-xs text-muted">Fit NVIDIA</p><h2 style={{ marginTop: '0.4rem' }}>{Math.round(fitScore * 100)}%</h2><p className="text-sm text-muted">Aderencia estimada, sujeita a POC</p></GlassPanel>
          <GlassPanel><p className="text-xs text-muted">Confianca da classificacao</p><h2 style={{ marginTop: '0.4rem' }}>{Math.round((assessment?.confidence ?? 0) * 100)}%</h2><p className="text-sm text-muted">Baseada nas evidencias validadas</p></GlassPanel>
        </div>
      )}

      <div className="tabs" role="tablist" aria-label="Detalhes da analise">
        {TABS.map((tab) => <button key={tab.id} role="tab" aria-selected={activeTab === tab.id} className={`tab ${activeTab === tab.id ? 'active' : ''}`} onClick={() => setActiveTab(tab.id)}>{tab.label}</button>)}
      </div>

      {analysisLoading ? <div className="empty-state"><Spinner size="lg" /><p>Carregando analise...</p></div> : analysisError ? (
        <div className="empty-state"><p className="text-error">Nao foi possivel carregar a analise: {analysisError}</p><Button onClick={loadAnalysis}>Tentar novamente</Button></div>
      ) : !latestRun ? <div className="empty-state"><p>Nenhuma analise registrada para esta startup.</p></div> : (
        <>
          {activeTab === 'diagnosis' && <DiagnosisTab analysis={analysis} />}
          {activeTab === 'evidences' && <EvidencesTab items={visibleEvidences} filter={evidenceFilter} onFilter={setEvidenceFilter} total={evidences.length} />}
          {activeTab === 'recommendations' && <RecommendationTab analysis={analysis} />}
          {activeTab === 'poc' && <POCBlueprintTab blueprint={pocBlueprint} startupName={startup.nome} />}
          {activeTab === 'impact' && <ImpactTab analysis={analysis} />}
          {activeTab === 'briefing' && <GlassPanel><div className="flex justify-between items-center gap-2 mb-4 flex-wrap"><h3>Briefing executivo</h3><div className="flex gap-2"><Button size="sm" variant="ghost" icon={<Copy size={14} />} onClick={copyBriefing}>{copyFeedback || 'Copiar'}</Button><Button size="sm" variant="ghost" icon={<Download size={14} />} onClick={downloadBriefing}>Markdown</Button><Button size="sm" variant="ghost" icon={<Printer size={14} />} onClick={() => window.print()}>PDF</Button></div></div>{briefing?.markdown && /\d+(?:[.,]\d+)?\s*%/.test(briefing.markdown) && <div className="card mb-3" style={{ borderColor: 'var(--status-warning)' }}><strong>Alegacoes quantitativas</strong><p className="text-sm text-muted mt-1">Confirme percentuais nas fontes da aba Evidencias antes de usa-los em decisoes externas.</p></div>}{briefing?.markdown ? <div className="markdown"><ReactMarkdown>{briefing.markdown}</ReactMarkdown></div> : <p className="text-muted">Briefing nao disponivel.</p>}</GlassPanel>}
          {activeTab === 'history' && <HistoryTab startup={startup} latestRunId={latestRun.id} />}
        </>
      )}
    </div>
  )
}

function DiagnosisTab({ analysis }: { analysis: RunAnalysis | null }) {
  const assessment = analysis?.assessment
  if (!assessment) return <GlassPanel><p className="text-muted">Diagnostico nao disponivel.</p></GlassPanel>
  return <div className="grid grid-2" style={{ gap: '1rem' }}>
    {assessment.review_required && <div className="card" style={{ gridColumn: '1 / -1', borderColor: 'var(--status-warning)', color: 'var(--status-warning)' }}><strong>Revisao humana recomendada</strong><p className="text-sm text-muted mt-1">{assessment.review_reason}</p></div>}
    <GlassPanel><h3>Classificacao de IA</h3><div className="mt-3"><MaturityBadge maturity={assessment.maturity_class} /></div><p className="text-sm text-muted mt-3" style={{ lineHeight: 1.6 }}>{assessment.evidence_summary}</p></GlassPanel>
    <GlassPanel><h3>Tecnologias utilizadas</h3><div className="flex flex-wrap gap-2 mt-3">{assessment.technologies.length ? assessment.technologies.map((technology) => <span className="badge badge-gray" key={technology} title={`Tecnologia identificada nas evidencias: ${technology}`}>{technology}</span>) : <p className="text-muted">Nenhuma tecnologia confirmada.</p>}</div></GlassPanel>
    <GlassPanel style={{ gridColumn: '1 / -1' }}><h3>Necessidades e limitacoes</h3><div className="grid grid-2 mt-3" style={{ gap: '0.75rem' }}>{assessment.limitations.length ? assessment.limitations.map((item) => <div className="card" key={item}>{item}</div>) : <p className="text-muted">Nenhuma limitacao registrada.</p>}</div></GlassPanel>
  </div>
}

function EvidencesTab({ items, filter, onFilter, total }: { items: Evidence[]; filter: string; onFilter: (value: string) => void; total: number }) {
  return <GlassPanel><div className="flex items-center justify-between gap-2 mb-4 flex-wrap"><div><h3>Evidencias coletadas</h3><p className="text-xs text-muted mt-1">{items.length} de {total} evidencias</p></div><select className="input" style={{ width: 180 }} value={filter} onChange={(event) => onFilter(event.target.value)} aria-label="Filtrar evidencias por confianca"><option value="all">Todas</option><option value="alta">Alta confianca</option><option value="media">Media confianca</option><option value="baixa">Baixa confianca</option></select></div><div className="evidence-list">{items.map((item) => <details className="card" key={item.id}><summary className="flex items-center justify-between gap-3"><span style={{ fontWeight: 600 }}>{item.source?.tipo_fonte ?? 'Fonte publica'}</span><span>{Math.round(item.score_confianca * 100)}% - {item.classificacao}</span></summary><p className="text-sm text-muted mt-3" style={{ lineHeight: 1.6 }}>{item.trecho}</p>{item.source?.url && <a href={item.source.url} target="_blank" rel="noopener noreferrer" className="text-sm" style={{ color: 'var(--accent)', overflowWrap: 'anywhere' }}>Abrir fonte <ExternalLink size={12} style={{ display: 'inline' }} /></a>}</details>)}</div>{items.length === 0 && <p className="text-muted">Nenhuma evidencia corresponde ao filtro.</p>}</GlassPanel>
}

function RecommendationTab({ analysis }: { analysis: RunAnalysis | null }) {
  const refinement = analysis?.refinement
  const recommendation = analysis?.recommendation
  return <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
    <GlassPanel><h3>Roadmap recomendado</h3><div className="grid grid-3 mt-3" style={{ gap: '0.75rem' }}>{Object.entries(refinement?.roadmap ?? {}).map(([horizon, content]) => <div className="card" key={horizon}><h4>{HORIZON_LABELS[horizon] ?? horizon}</h4><div className="flex flex-wrap gap-1 mt-2">{content.tecnologias.map((technology) => <span className="badge badge-green" key={technology}>{technology}</span>)}</div>{content.acoes.map((action) => <p className="text-sm text-muted mt-2" key={action}>{action}</p>)}</div>)}</div></GlassPanel>
    <GlassPanel><h3>Tecnologias NVIDIA priorizadas</h3><div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1rem' }}>{refinement?.technologies.length ? refinement.technologies.map((item) => <div className="card" key={item.tecnologia}><div className="flex justify-between gap-2 flex-wrap"><strong>{item.tecnologia}</strong><span className="badge badge-gray">Complexidade {item.complexidade}</span></div><p className="text-sm mt-2">{item.problema_resolvido}</p><p className="text-sm text-muted mt-2">{item.beneficio}</p><p className="text-xs text-muted mt-2">Risco: {item.riscos}</p><div className="mt-2">{item.fontes_evidencia.map((url) => <a key={url} href={url} target="_blank" rel="noopener noreferrer" className="text-xs" style={{ display: 'block', color: 'var(--accent)', overflowWrap: 'anywhere' }}>{url}</a>)}</div></div>) : recommendation?.technologies.map((item) => <div className="card" key={item.name}><strong>{item.name}</strong><p className="text-sm text-muted mt-2">{item.rationale}</p></div>)}</div></GlassPanel>
    {!!refinement?.startup_questions.length && <GlassPanel><h3>Proximos passos</h3><ol style={{ paddingLeft: '1.25rem', marginTop: '0.75rem' }}>{refinement.startup_questions.map((question) => <li className="text-sm text-muted mb-2" key={question}>{question}</li>)}</ol></GlassPanel>}
  </div>
}

function POCBlueprintTab({ blueprint, startupName }: { blueprint: POCBlueprint | null; startupName: string }) {
  const download = () => {
    if (!blueprint?.markdown) return
    const blob = new Blob([blueprint.markdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${startupName}-poc-blueprint.md`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return <GlassPanel>
    <div className="flex justify-between gap-2 mb-4">
      <div>
        <h3>NVIDIA POC Blueprint</h3>
        <p className="text-sm text-muted mt-1">Plano mensurável, sem promessa de ganho antes do benchmark.</p>
      </div>
      <Button size="sm" variant="ghost" icon={<Download size={14} />} onClick={download}>Markdown</Button>
    </div>
    {blueprint?.markdown
      ? <div className="markdown"><ReactMarkdown>{blueprint.markdown}</ReactMarkdown></div>
      : <p className="text-muted">Blueprint indisponível.</p>}
  </GlassPanel>
}

function ImpactTab({ analysis }: { analysis: RunAnalysis | null }) {
  const impact = analysis?.impact
  if (!impact) return <GlassPanel><p className="text-muted">Estimativa de impacto nao disponivel.</p></GlassPanel>
  return <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}><GlassPanel><div className="flex items-center gap-4"><ProgressRing value={impact.aggregate_index ?? 0} label={String(impact.aggregate_index ?? 0)} sublabel="/100" /><div><h3>Indice interno de potencial</h3><p className="text-sm text-muted mt-2">{impact.estimated_impact}</p></div></div></GlassPanel><div className="grid grid-2" style={{ gap: '1rem' }}><GlassPanel><h3>KPIs para a prova de conceito</h3><ul style={{ paddingLeft: '1.25rem', marginTop: '0.75rem' }}>{impact.suggested_kpis.map((item) => <li className="text-sm text-muted mb-2" key={item}>{item}</li>)}</ul></GlassPanel><GlassPanel><h3>Incertezas e premissas</h3><ul style={{ paddingLeft: '1.25rem', marginTop: '0.75rem' }}>{impact.uncertainties.map((item) => <li className="text-sm text-muted mb-2" key={item}>{item}</li>)}</ul></GlassPanel></div>{impact.estimates.map((estimate) => <GlassPanel key={estimate.tecnologia}><h3>{estimate.tecnologia}</h3><p className="text-sm text-muted mt-2">{estimate.impacto_negocio}</p><p className="text-xs text-muted mt-2">Confianca: {estimate.confianca}. Valores devem ser medidos contra o baseline da startup.</p></GlassPanel>)}</div>
}

function HistoryTab({ startup, latestRunId }: { startup: NonNullable<ReturnType<typeof useStartup>['startup']>; latestRunId: string }) {
  return <GlassPanel><h3>Historico de execucoes</h3><div className="table-wrapper mt-3"><table><thead><tr><th>Execucao</th><th>Status</th><th>Estagio</th><th>Duracao</th><th>Data</th></tr></thead><tbody>{startup.pipeline_runs?.map((run) => <tr key={run.id}><td>{run.id === latestRunId ? 'Mais recente' : run.id.split('-')[0]}</td><td><StatusBadge status={run.status} /></td><td>{run.current_stage ?? 'Nao informado'}</td><td>{run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : '-'}</td><td>{new Date(run.created_at).toLocaleString('pt-BR')}</td></tr>)}</tbody></table></div>{startup.pipeline_runs?.[0] && <div className="mt-4"><h3 style={{ marginBottom: '0.75rem' }}>Estagios da ultima execucao</h3><PipelineTimeline run={startup.pipeline_runs[0]} /></div>}</GlassPanel>
}
