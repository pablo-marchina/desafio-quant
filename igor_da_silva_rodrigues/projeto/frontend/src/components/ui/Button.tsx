import React from 'react'
import { motion } from 'framer-motion'
import { Spinner } from './Spinner'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type ButtonSize = 'sm' | 'md' | 'lg' | 'icon'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  icon?: React.ReactNode
  children?: React.ReactNode
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'secondary',
  size = 'md',
  loading = false,
  icon,
  children,
  disabled,
  className = '',
  ...props
}) => {
  const sizeClass = size === 'md' ? '' : `btn-${size}`

  return (
    <motion.button
      whileHover={{ scale: disabled || loading ? 1 : 1.02 }}
      whileTap={{ scale: disabled || loading ? 1 : 0.97 }}
      transition={{ duration: 0.15 }}
      className={`btn btn-${variant} ${sizeClass} ${className}`}
      disabled={disabled || loading}
      {...(props as React.ComponentPropsWithRef<typeof motion.button>)}
    >
      {loading ? <Spinner size="sm" /> : icon}
      {children}
    </motion.button>
  )
}
