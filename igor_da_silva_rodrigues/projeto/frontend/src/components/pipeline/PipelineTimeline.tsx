import React from 'react'
import { motion } from 'framer-motion'
import { Check, Loader2, X, Clock, ChevronRight } from 'lucide-react'
import type { PipelineRunSummary } from '@/types/api'

const STAGES = [
  'search_planner',
  'scraper',
  'evidence_validator',
  'ai_maturity_classifier',
  'inception_fit',
  'nvidia_recommender',
  'recommendation',
  'impact_estimator',
  'briefing_generator',
]

const STAGE_LABELS: Record<string, string> = {
  search_planner:         'Search Planner',
  scraper:                'Scraper',
  evidence_validator:     'Evidence Validator',
  ai_maturity_classifier: 'AI Maturity Classifier',
  inception_fit:          'Inception Fit',
  nvidia_recommender:     'NVIDIA Recommender RAG',
  recommendation:         'Recommendation',
  impact_estimator:       'Impact Estimator',
  briefing_generator:     'Briefing Generator',
}

function getStageState(
  stageName: string,
  run: PipelineRunSummary
): 'completed' | 'running' | 'failed' | 'pending' {
  if (run.status === 'completed') return 'completed'
  if (run.status === 'cancelled') return 'pending'
  if (!run.current_stage) {
    return 'pending'
  }
  const currentIdx = STAGES.indexOf(run.current_stage)
  const stageIdx   = STAGES.indexOf(stageName)
  if (stageIdx < currentIdx) return 'completed'
  if (stageIdx === currentIdx) {
    return run.status === 'failed' ? 'failed' : 'running'
  }
  return 'pending'
}

interface PipelineTimelineProps { run: PipelineRunSummary }

export const PipelineTimeline: React.FC<PipelineTimelineProps> = ({ run }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
    {STAGES.map((stage, i) => {
      const state = getStageState(stage, run)
      const icon = {
        completed: <Check size={14} />,
        running:   <Loader2 size={14} className="animate-spin" />,
        failed:    <X size={14} />,
        pending:   <Clock size={14} />,
      }[state]

      const colors = {
        completed: { bg: 'rgba(118,185,0,0.15)', border: 'rgba(118,185,0,0.4)', icon: 'var(--accent)', text: 'var(--text-primary)' },
        running:   { bg: 'rgba(14,165,233,0.12)', border: 'rgba(14,165,233,0.4)', icon: 'var(--status-running)', text: 'var(--text-primary)' },
        failed:    { bg: 'rgba(232,64,64,0.12)', border: 'rgba(232,64,64,0.4)', icon: 'var(--status-error)', text: 'var(--text-primary)' },
        pending:   { bg: 'transparent', border: 'var(--border-subtle)', icon: 'var(--text-muted)', text: 'var(--text-muted)' },
      }[state]

      return (
        <motion.div
          key={stage}
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.04, duration: 0.2 }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            padding: '0.5rem 0.75rem',
            borderRadius: 'var(--radius-md)',
            background: colors.bg,
            border: `1px solid ${colors.border}`,
          }}
        >
          <span style={{ color: colors.icon, flexShrink: 0 }}>{icon}</span>
          <span style={{ fontSize: '0.8rem', color: colors.text, fontWeight: state === 'pending' ? 400 : 500 }}>
            {i + 1}. {STAGE_LABELS[stage] ?? stage}
          </span>
          {state === 'running' && (
            <ChevronRight size={13} style={{ marginLeft: 'auto', color: 'var(--status-running)' }} />
          )}
        </motion.div>
      )
    })}
  </div>
)
