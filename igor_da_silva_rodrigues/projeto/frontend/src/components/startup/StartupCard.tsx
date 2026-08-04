import React from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { ExternalLink, MapPin, Tag, Clock } from 'lucide-react'
import { MaturityBadge, StatusBadge } from '@/components/ui/Badge'
import type { Startup } from '@/types/api'
import type { MaturityClass } from '@/types/api'

interface StartupCardProps {
  startup: Startup
  maturity?: MaturityClass
}

export const StartupCard: React.FC<StartupCardProps> = ({ startup, maturity }) => {
  const navigate = useNavigate()
  const latestRun = startup.pipeline_runs?.[0]

  return (
    <motion.div
      className="card card-hover"
      whileHover={{ y: -4, scale: 1.01 }}
      transition={{ duration: 0.2 }}
      onClick={() => navigate(`/startups/${startup.id}`)}
      style={{ cursor: 'pointer' }}
      data-testid="startup-card"
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <h3
          style={{
            fontFamily: 'var(--font-heading)',
            fontSize: '1rem',
            fontWeight: 700,
            color: 'var(--text-primary)',
            lineHeight: 1.3,
          }}
        >
          {startup.nome}
        </h3>
        {startup.site_oficial && (
          <a
            href={startup.site_oficial}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="btn btn-ghost btn-icon"
            style={{ padding: '0.2rem', color: 'var(--text-muted)', flexShrink: 0 }}
            aria-label={`Visitar site de ${startup.nome}`}
          >
            <ExternalLink size={13} />
          </a>
        )}
      </div>

      <div className="flex flex-col gap-2 mb-3">
        {startup.categoria && (
          <div className="flex items-center gap-1 text-xs text-muted">
            <Tag size={11} />
            <span>{startup.categoria}</span>
          </div>
        )}
        {(startup.cidade || startup.estado) && (
          <div className="flex items-center gap-1 text-xs text-muted">
            <MapPin size={11} />
            <span>{[startup.cidade, startup.estado].filter(Boolean).join(', ')}</span>
          </div>
        )}
        {latestRun?.created_at && (
          <div className="flex items-center gap-1 text-xs text-muted">
            <Clock size={11} />
            <span>{new Date(latestRun.created_at).toLocaleDateString('pt-BR')}</span>
          </div>
        )}
      </div>

      {startup.descricao_curta && (
        <p className="text-sm text-muted mb-3" style={{ lineHeight: 1.5 }}>
          {startup.descricao_curta}
        </p>
      )}

      <div className="flex items-center justify-between flex-wrap gap-2">
        {maturity ? (
          <MaturityBadge maturity={maturity} />
        ) : (
          <span className="text-xs text-muted">Não analisada</span>
        )}
        {latestRun && (
          <StatusBadge status={latestRun.status} />
        )}
      </div>
      <div className="flex justify-between text-xs text-muted mt-2">
        <span>Nivel {startup.maturity_level ?? '—'}/5</span>
        <span>Fit {startup.fit_score === null || startup.fit_score === undefined ? '—' : `${Math.round(startup.fit_score * 100)}%`}</span>
      </div>
    </motion.div>
  )
}
