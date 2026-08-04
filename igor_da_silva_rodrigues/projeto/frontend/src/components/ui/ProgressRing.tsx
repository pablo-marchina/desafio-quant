import React from 'react'
import { motion } from 'framer-motion'

interface ProgressRingProps {
  value: number      // 0–100
  size?: number
  stroke?: number
  label?: string
  sublabel?: string
  color?: string
}

export const ProgressRing: React.FC<ProgressRingProps> = ({
  value,
  size = 100,
  stroke = 8,
  label,
  sublabel,
  color = 'var(--accent)',
}) => {
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (Math.min(Math.max(value, 0), 100) / 100) * circumference

  return (
    <div
      style={{ position: 'relative', width: size, height: size, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}
      data-testid="progress-ring"
    >
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        {/* Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--bg-surface-3)"
          strokeWidth={stroke}
        />
        {/* Progress */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, ease: 'easeOut', delay: 0.2 }}
          style={{ filter: `drop-shadow(0 0 6px ${color})` }}
        />
      </svg>

      {/* Center text */}
      {(label !== undefined || sublabel !== undefined) && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {label !== undefined && (
            <span
              style={{
                fontFamily: 'var(--font-heading)',
                fontWeight: 700,
                fontSize: size > 80 ? '1.1rem' : '0.8rem',
                color: 'var(--text-primary)',
                lineHeight: 1,
              }}
            >
              {label}
            </span>
          )}
          {sublabel && (
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              {sublabel}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
