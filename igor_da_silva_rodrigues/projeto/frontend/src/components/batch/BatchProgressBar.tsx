import React from 'react'
import type { Batch } from '@/types/api'

interface BatchProgressBarProps {
  batch: Batch
  height?: number
}

export const BatchProgressBar: React.FC<BatchProgressBarProps> = ({ batch, height = 8 }) => {
  const { total_items, completed_items, failed_items, partial_items } = batch
  const total = total_items || 1
  const pending = Math.max(0, total - completed_items - failed_items - partial_items)

  const pct = (n: number) => `${Math.min(100, (n / total) * 100).toFixed(1)}%`

  const segments = [
    { label: `Concluídos: ${completed_items}`, value: completed_items, color: 'var(--status-success)' },
    { label: `Parciais: ${partial_items}`,     value: partial_items,   color: 'var(--status-partial)' },
    { label: `Falhos: ${failed_items}`,         value: failed_items,    color: 'var(--status-error)' },
    { label: `Pendentes: ${pending}`,           value: pending,         color: 'var(--bg-surface-3)' },
  ]

  const totalDone = completed_items + partial_items
  const overallPct = Math.round((totalDone / total) * 100)

  return (
    <div data-testid="batch-progress-bar">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-muted">Progresso</span>
        <span
          style={{
            fontFamily: 'var(--font-heading)',
            fontWeight: 700,
            fontSize: '0.875rem',
            color: 'var(--accent)',
          }}
        >
          {overallPct}%
        </span>
      </div>

      <div
        style={{
          height,
          borderRadius: height,
          background: 'var(--bg-surface-3)',
          overflow: 'hidden',
          display: 'flex',
        }}
        role="progressbar"
        aria-valuenow={overallPct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Progresso do lote: ${overallPct}%`}
      >
        {segments.map((seg) =>
          seg.value > 0 ? (
            <div
              key={seg.label}
              title={seg.label}
              style={{
                width: pct(seg.value),
                background: seg.color,
                transition: 'width 0.5s ease',
              }}
            />
          ) : null
        )}
      </div>

      <div className="flex gap-3 mt-2 flex-wrap">
        {segments.slice(0, 3).map((seg) => (
          <div key={seg.label} className="flex items-center gap-1">
            <span style={{ width: 8, height: 8, borderRadius: 2, background: seg.color, display: 'inline-block' }} />
            <span className="text-xs text-muted">{seg.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
