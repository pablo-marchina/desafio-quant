import React from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { Layers, Play, RotateCcw, Ban } from 'lucide-react'
import { StatusBadge } from '@/components/ui/Badge'
import { BatchProgressBar } from './BatchProgressBar'
import { Button } from '@/components/ui/Button'
import type { Batch } from '@/types/api'

interface BatchCardProps {
  batch: Batch
  onRun?: (id: string) => void
  onResume?: (id: string) => void
  onCancel?: (id: string) => void
  acting?: boolean
}

export const BatchCard: React.FC<BatchCardProps> = ({
  batch,
  onRun,
  onResume,
  onCancel,
  acting = false,
}) => {
  const navigate = useNavigate()
  const canRun    = batch.status === 'pending' || batch.status === 'created'
  const canResume = ['partial', 'failed', 'cancelled'].includes(batch.status)
  const canCancel = batch.status === 'running'

  return (
    <motion.div
      className="card card-hover"
      whileHover={{ y: -3 }}
      transition={{ duration: 0.2 }}
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <Layers size={16} style={{ color: 'var(--accent)' }} />
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.75rem',
              color: 'var(--text-muted)',
            }}
          >
            {batch.id.split('-')[0]}…
          </span>
        </div>
        <StatusBadge status={batch.status} />
      </div>

      <div className="flex gap-4 mb-3 text-sm">
        <div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Total</div>
          <div style={{ fontFamily: 'var(--font-heading)', fontWeight: 700, color: 'var(--text-primary)', fontSize: '1.25rem' }}>
            {batch.total_items}
          </div>
        </div>
        <div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Concluídos</div>
          <div style={{ fontFamily: 'var(--font-heading)', fontWeight: 700, color: 'var(--status-success)', fontSize: '1.25rem' }}>
            {batch.completed_items}
          </div>
        </div>
        <div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Falhos</div>
          <div style={{ fontFamily: 'var(--font-heading)', fontWeight: 700, color: 'var(--status-error)', fontSize: '1.25rem' }}>
            {batch.failed_items}
          </div>
        </div>
      </div>

      <BatchProgressBar batch={batch} />

      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.75rem' }}>
        Criado em {new Date(batch.created_at).toLocaleString('pt-BR')}
      </div>

      <div className="flex gap-2 mt-3 flex-wrap">
        {canRun && onRun && (
          <Button
            size="sm" variant="primary" icon={<Play size={13} />}
            onClick={() => onRun?.(batch.id)} loading={acting}
          >
            Executar
          </Button>
        )}
        {canResume && onResume && (
          <Button
            size="sm" variant="secondary" icon={<RotateCcw size={13} />}
            onClick={() => onResume?.(batch.id)} loading={acting}
          >
            Retomar
          </Button>
        )}
        {canCancel && onCancel && (
          <Button
            size="sm" variant="danger" icon={<Ban size={13} />}
            onClick={() => onCancel?.(batch.id)} loading={acting}
          >
            Cancelar
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={() => navigate(`/batches/${batch.id}`)}>
          Detalhes
        </Button>
      </div>
    </motion.div>
  )
}
