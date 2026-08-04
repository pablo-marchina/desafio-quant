import { ArrowLeft, RefreshCw } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import { BatchProgressBar } from '@/components/batch/BatchProgressBar'
import { DeadLetterTable } from '@/components/batch/DeadLetterTable'
import { Button } from '@/components/ui/Button'
import { GlassPanel } from '@/components/ui/GlassPanel'
import { Spinner } from '@/components/ui/Spinner'
import { StatusBadge } from '@/components/ui/Badge'
import { useBatch } from '@/hooks/useBatches'
import { useAuthStore } from '@/store/authStore'

export default function BatchDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const role = useAuthStore((state) => state.role)
  const {
    batch,
    items,
    deadLetters,
    loading,
    error,
    acting,
    refetch,
    handleRun,
    handleResume,
    handleCancel,
    handleReplay,
  } = useBatch(id, 5_000)

  if (loading && !batch) {
    return <div className="empty-state"><Spinner size="lg" /><p>Carregando lote...</p></div>
  }

  if (error || !batch) {
    return (
      <div className="empty-state">
        <p className="text-error">{error ?? 'Lote nao encontrado'}</p>
        <Button variant="secondary" onClick={() => navigate('/batches')}>Voltar</Button>
      </div>
    )
  }

  const canOperate = role === 'admin' || role === 'analyst'
  const canRun = canOperate && (batch.status === 'pending' || batch.status === 'created')
  const canResume = canOperate && ['partial', 'failed', 'cancelled'].includes(batch.status)
  const canCancel = role === 'admin' && batch.status === 'running'

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <Button variant="ghost" icon={<ArrowLeft size={15} />} onClick={() => navigate('/batches')}>
          Lotes
        </Button>
        <Button variant="ghost" icon={<RefreshCw size={14} />} onClick={refetch} loading={loading}>
          Atualizar
        </Button>
      </div>

      <GlassPanel style={{ marginBottom: '1rem' }}>
        <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
          <div>
            <h2 style={{ fontSize: '1rem' }}>Lote {batch.id.split('-')[0]}</h2>
            <p className="text-xs text-muted mt-1">
              Criado em {new Date(batch.created_at).toLocaleString('pt-BR')}
            </p>
          </div>
          <StatusBadge status={batch.status} />
        </div>
        <BatchProgressBar batch={batch} />
        {canOperate && (
          <div className="flex gap-2 mt-4 flex-wrap">
            {canRun && <Button onClick={handleRun} loading={acting}>Executar</Button>}
            {canResume && <Button variant="secondary" onClick={() => handleResume(false)} loading={acting}>Retomar</Button>}
            {canCancel && <Button variant="danger" onClick={handleCancel} loading={acting}>Cancelar</Button>}
          </div>
        )}
      </GlassPanel>

      <GlassPanel style={{ marginBottom: '1rem' }}>
        <h3 style={{ fontSize: '0.95rem', marginBottom: '1rem' }}>Startups do lote</h3>
        <div className="table-wrapper">
          <table>
            <thead><tr><th>Startup</th><th>Status</th><th>Tentativas</th><th>Resultado</th></tr></thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td style={{ fontWeight: 600 }}>{item.startup_name ?? item.startup_id}</td>
                  <td><StatusBadge status={item.status} /></td>
                  <td>{item.attempt_count}</td>
                  <td className="text-xs text-muted">{item.error_message ?? (item.pipeline_run_id ? 'Analise disponivel' : 'Aguardando')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassPanel>

      {deadLetters.length > 0 && (
        <GlassPanel>
          <h3 style={{ fontSize: '0.95rem', marginBottom: '1rem' }}>Falhas para revisao</h3>
          <DeadLetterTable
            items={deadLetters}
            onReplay={role === 'admin' ? handleReplay : undefined}
            acting={acting}
          />
        </GlassPanel>
      )}
    </div>
  )
}
