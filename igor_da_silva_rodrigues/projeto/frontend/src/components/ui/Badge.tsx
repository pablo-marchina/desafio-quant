import React from 'react'
import type { MaturityClass, RunStatus, BatchStatus, BatchItemStatus } from '@/types/api'

type BadgeVariant =
  | 'green' | 'blue' | 'purple' | 'gray' | 'warning' | 'error' | 'sky'

interface BadgeProps {
  children: React.ReactNode
  variant?: BadgeVariant
  className?: string
  dot?: boolean
}

export const Badge: React.FC<BadgeProps> = ({ children, variant = 'gray', className = '', dot = false }) => (
  <span className={`badge badge-${variant} ${className}`} data-testid="badge">
    {dot && (
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: 'currentColor',
          display: 'inline-block',
          flexShrink: 0,
        }}
      />
    )}
    {children}
  </span>
)

// ---- Maturity Badge ----
const MATURITY_MAP: Record<MaturityClass, { label: string; variant: BadgeVariant }> = {
  'AI-native':    { label: 'AI-native',    variant: 'green' },
  'AI-enabled':   { label: 'AI-enabled',   variant: 'blue' },
  'API-consumer': { label: 'API-consumer', variant: 'purple' },
  'Non-AI':       { label: 'Non-AI',       variant: 'gray' },
  'unknown':      { label: 'Desconhecido', variant: 'gray' },
}

interface MaturityBadgeProps { maturity: MaturityClass; className?: string }

export const MaturityBadge: React.FC<MaturityBadgeProps> = ({ maturity, className = '' }) => {
  const { label, variant } = MATURITY_MAP[maturity] ?? MATURITY_MAP['unknown']
  return <Badge variant={variant} className={className} dot>{label}</Badge>
}

// ---- Run Status Badge ----
const STATUS_MAP: Record<RunStatus | BatchStatus | BatchItemStatus, { label: string; variant: BadgeVariant }> = {
  pending:   { label: 'Pendente',   variant: 'gray' },
  running:   { label: 'Executando', variant: 'sky' },
  completed: { label: 'Concluído',  variant: 'green' },
  partial:   { label: 'Parcial',    variant: 'purple' },
  failed:    { label: 'Falhou',     variant: 'error' },
  cancelled: { label: 'Cancelado',  variant: 'warning' },
  created:   { label: 'Criado',     variant: 'gray' },
}

interface StatusBadgeProps { status: string; className?: string }

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '' }) => {
  const mapped = STATUS_MAP[status as RunStatus] ?? { label: status, variant: 'gray' as BadgeVariant }
  return (
    <Badge variant={mapped.variant} className={className} dot>
      {mapped.label}
    </Badge>
  )
}
