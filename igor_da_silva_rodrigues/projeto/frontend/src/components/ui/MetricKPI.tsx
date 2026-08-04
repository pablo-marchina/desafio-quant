import React from 'react'
import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface MetricKPIProps {
  label: string
  value: number | string
  unit?: string
  trend?: number
  icon?: React.ReactNode
  format?: 'number' | 'percent' | 'duration' | 'string'
  id?: string
}

function formatValue(value: number | string, format: MetricKPIProps['format']): string {
  if (typeof value === 'string') return value
  switch (format) {
    case 'percent':
      return `${value.toFixed(1)}%`
    case 'duration':
      if (value < 1000) return `${Math.round(value)}ms`
      if (value < 60000) return `${(value / 1000).toFixed(1)}s`
      return `${(value / 60000).toFixed(1)}min`
    case 'number':
    default:
      return value >= 1000 ? `${(value / 1000).toFixed(1)}k` : String(Math.round(value))
  }
}

export const MetricKPI: React.FC<MetricKPIProps> = ({
  label,
  value,
  unit,
  trend,
  icon,
  format = 'number',
  id,
}) => {
  const TrendIcon =
    trend === undefined || trend === 0 ? Minus : trend > 0 ? TrendingUp : TrendingDown
  const trendColor =
    trend === undefined || trend === 0
      ? 'var(--text-muted)'
      : trend > 0
        ? 'var(--status-success)'
        : 'var(--status-error)'

  return (
    <motion.div
      id={id}
      className="card glass-hover"
      whileHover={{ y: -3 }}
      transition={{ duration: 0.2 }}
      data-testid="metric-kpi"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-muted" style={{ letterSpacing: '0.06em', textTransform: 'uppercase', fontWeight: 600 }}>
          {label}
        </span>
        {icon && (
          <span style={{ color: 'var(--accent)', opacity: 0.8 }}>{icon}</span>
        )}
      </div>

      <div className="flex items-end gap-2">
        <motion.span
          style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'clamp(1.75rem, 3vw, 2.25rem)',
            fontWeight: 700,
            lineHeight: 1,
            color: 'var(--text-primary)',
          }}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.35 }}
        >
          {formatValue(value as number, format)}
        </motion.span>
        {unit && (
          <span className="text-muted text-sm mb-1">{unit}</span>
        )}
      </div>

      {trend !== undefined && (
        <div className="flex items-center gap-1 mt-2" style={{ color: trendColor }}>
          <TrendIcon size={13} />
          <span className="text-xs" style={{ fontWeight: 600 }}>
            {trend > 0 ? '+' : ''}{trend.toFixed(1)}%
          </span>
          <span className="text-xs text-muted">vs. ontem</span>
        </div>
      )}
    </motion.div>
  )
}
