import React from 'react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import type { MaturityClass } from '@/types/api'

const COLORS: Record<string, string> = {
  'AI-native':    'var(--maturity-ai-native)',
  'AI-enabled':   'var(--maturity-ai-enabled)',
  'API-consumer': 'var(--maturity-api-consumer)',
  'Non-AI':       'var(--maturity-non-ai)',
  'unknown':      'var(--maturity-unknown)',
}

interface MaturityDistributionProps {
  data: Record<string, number>
}

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: { name: string; value: number }[] }) => {
  if (!active || !payload?.length) return null
  const { name, value } = payload[0]
  return (
    <div
      style={{
        background: 'var(--bg-surface-2)',
        border: '1px solid var(--border-default)',
        borderRadius: 'var(--radius-md)',
        padding: '0.5rem 0.875rem',
        fontSize: '0.8rem',
      }}
    >
      <div style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{name}</div>
      <div style={{ color: 'var(--text-muted)' }}>{value} startup{value !== 1 ? 's' : ''}</div>
    </div>
  )
}

export const MaturityDistribution: React.FC<MaturityDistributionProps> = ({ data }) => {
  const entries = Object.entries(data)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }))

  if (entries.length === 0) {
    return (
      <div className="empty-state" style={{ padding: '2rem' }}>
        <p>Sem dados de maturidade.</p>
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie
          data={entries}
          cx="50%"
          cy="50%"
          innerRadius={65}
          outerRadius={100}
          paddingAngle={3}
          dataKey="value"
        >
          {entries.map((entry) => (
            <Cell
              key={entry.name}
              fill={COLORS[entry.name as MaturityClass] ?? '#374151'}
              stroke="transparent"
            />
          ))}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
        <Legend
          formatter={(value) => (
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.78rem' }}>{value}</span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}
