import React from 'react'
import { RotateCcw, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import type { DeadLetter } from '@/types/api'

interface DeadLetterTableProps {
  items: DeadLetter[]
  onReplay?: (id: string) => void
  acting?: boolean
}

export const DeadLetterTable: React.FC<DeadLetterTableProps> = ({ items, onReplay, acting = false }) => {
  if (items.length === 0) {
    return (
      <div className="empty-state">
        <AlertTriangle size={32} className="empty-state-icon" />
        <p>Nenhuma dead letter neste lote.</p>
      </div>
    )
  }

  return (
    <div className="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Startup</th>
            <th>Categoria</th>
            <th>Tentativas</th>
            <th>Erro</th>
            <th>Criado em</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((dl) => (
            <tr key={dl.id}>
              <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                {dl.id.split('-')[0]}…
              </td>
              <td style={{ fontWeight: 600 }}>{dl.startup_name ?? dl.batch_item_id.split('-')[0]}</td>
              <td>{dl.error_category ?? '—'}</td>
              <td>{dl.attempt_count}</td>
              <td
                style={{
                  maxWidth: 240,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  fontSize: '0.78rem',
                  color: 'var(--status-error)',
                }}
                title={dl.error_message ?? undefined}
              >
                {dl.error_message ?? '—'}
              </td>
              <td style={{ fontSize: '0.75rem' }}>
                {new Date(dl.created_at).toLocaleString('pt-BR')}
              </td>
              <td>
                {onReplay && <Button
                  size="sm"
                  variant="secondary"
                  icon={<RotateCcw size={12} />}
                  onClick={() => onReplay(dl.id)}
                  loading={acting}
                >
                  Replay
                </Button>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
