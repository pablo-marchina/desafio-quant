import React from 'react'
import { motion } from 'framer-motion'

interface GlassPanelProps {
  children: React.ReactNode
  className?: string
  hover?: boolean
  padding?: boolean
  style?: React.CSSProperties
}

export const GlassPanel: React.FC<GlassPanelProps> = ({
  children,
  className = '',
  hover = false,
  padding = true,
  style,
}) => (
  <motion.div
    className={`glass ${hover ? 'glass-hover' : ''} ${padding ? 'card' : ''} ${className}`}
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.3 }}
    style={style}
  >
    {children}
  </motion.div>
)
