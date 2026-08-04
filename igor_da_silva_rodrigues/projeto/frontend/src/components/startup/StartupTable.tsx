import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronUp, ChevronDown, ExternalLink } from 'lucide-react'
import { MaturityBadge, StatusBadge } from '@/components/ui/Badge'
import type { Startup } from '@/types/api'
import type { MaturityClass } from '@/types/api'

type SortKey = 'nome' | 'categoria' | 'cidade' | 'created_at'

interface StartupTableProps {
  startups: Startup[]
  maturityMap?: Record<string, MaturityClass>
}

export const StartupTable: React.FC<StartupTableProps> = ({ startups, maturityMap = {} }) => {
  const navigate = useNavigate()
  const [sortKey, setSortKey] = useState<SortKey>('created_at')
  const [sortAsc, setSortAsc] = useState(false)

  const sorted = [...startups].sort((a, b) => {
    const av = a[sortKey] ?? ''
    const bv = b[sortKey] ?? ''
    return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av))
  })

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) setSortAsc((v) => !v)
    else { setSortKey(key); setSortAsc(true) }
  }

  const SortIcon = ({ k }: { k: SortKey }) =>
    sortKey === k ? (
      sortAsc ? <ChevronUp size={13} /> : <ChevronDown size={13} />
    ) : (
      <ChevronDown size={13} style={{ opacity: 0.3 }} />
    )

  return (
    <div className="table-wrapper">
      <table>
        <thead>
          <tr>
            <th className="sortable" onClick={() => toggleSort('nome')}>
              <span className="flex items-center gap-1">Nome <SortIcon k="nome" /></span>
            </th>
            <th className="sortable" onClick={() => toggleSort('categoria')}>
              <span className="flex items-center gap-1">Categoria <SortIcon k="categoria" /></span>
            </th>
            <th className="sortable" onClick={() => toggleSort('cidade')}>
              <span className="flex items-center gap-1">Cidade <SortIcon k="cidade" /></span>
            </th>
            <th>Classificacao</th>
            <th>Nivel</th>
            <th>Fit NVIDIA</th>
            <th>Última Execução</th>
            <th>Site</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((s) => {
            const latestRun = s.pipeline_runs?.[0]
            const maturity = maturityMap[s.id]
            return (
              <tr
                key={s.id}
                style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/startups/${s.id}`)}
                role="row"
                aria-label={`Ver startup ${s.nome}`}
              >
                <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                  {s.nome}
                </td>
                <td>{s.categoria ?? '—'}</td>
                <td>{[s.cidade, s.estado].filter(Boolean).join(', ') || '—'}</td>
                <td>
                  {maturity ? (
                    <MaturityBadge maturity={maturity} />
                  ) : (
                    <span className="text-xs text-muted">—</span>
                  )}
                </td>
                <td>{s.maturity_level === null || s.maturity_level === undefined ? '—' : `${s.maturity_level}/5`}</td>
                <td>{s.fit_score === null || s.fit_score === undefined ? '—' : `${Math.round(s.fit_score * 100)}%`}</td>
                <td>
                  {latestRun ? (
                    <StatusBadge status={latestRun.status} />
                  ) : (
                    <span className="text-xs text-muted">—</span>
                  )}
                </td>
                <td>
                  {s.site_oficial ? (
                    <a
                      href={s.site_oficial}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="btn btn-ghost btn-icon"
                      style={{ padding: '0.25rem', color: 'var(--text-muted)' }}
                      aria-label={`Site de ${s.nome}`}
                    >
                      <ExternalLink size={13} />
                    </a>
                  ) : '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
