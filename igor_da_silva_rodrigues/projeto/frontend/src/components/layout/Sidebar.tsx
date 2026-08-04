import React, { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LayoutDashboard,
  Rocket,
  Layers,
  LogOut,
  ChevronRight,
  Activity,
} from 'lucide-react'
import { NvidiaLogo } from '@/components/ui/NvidiaLogo'
import { useAuthStore } from '@/store/authStore'
import { getReadiness } from '@/lib/api'

const navItems = [
  { to: '/',         label: 'Dashboard',  icon: LayoutDashboard, end: true },
  { to: '/startups', label: 'Startups',   icon: Rocket },
  { to: '/batches',  label: 'Lotes',      icon: Layers },
]

export const Sidebar: React.FC = () => {
  const { user, role, signOut } = useAuthStore()
  const location = useLocation()
  const [systemStatus, setSystemStatus] = useState<'ready' | 'degraded' | 'offline' | null>(null)

  useEffect(() => {
    const check = () => getReadiness().then((result) => setSystemStatus(result.status)).catch(() => setSystemStatus('offline'))
    void check()
    const interval = window.setInterval(check, 30_000)
    return () => window.clearInterval(interval)
  }, [])

  return (
    <aside className="desktop-sidebar"
      style={{
        position: 'fixed',
        left: 0,
        top: 0,
        bottom: 0,
        width: 'var(--sidebar-width)',
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 50,
        backdropFilter: 'blur(20px)',
      }}
    >
      {/* Logo */}
      <div
        style={{
          height: 'var(--header-height)',
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
          padding: '0 1.25rem',
          borderBottom: '1px solid var(--border-subtle)',
        }}
      >
        <NvidiaLogo size={28} />
        <div>
          <div
            style={{
              fontFamily: 'var(--font-heading)',
              fontWeight: 700,
              fontSize: '0.9rem',
              color: 'var(--text-primary)',
              lineHeight: 1.2,
            }}
          >
            AI Radar
          </div>
          <div style={{ fontSize: '0.65rem', color: 'var(--accent)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            NVIDIA Inception
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '1rem 0.75rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        {navItems.map(({ to, label, icon: Icon, end }) => {
          const active = end ? location.pathname === to : location.pathname.startsWith(to)
          return (
            <NavLink key={to} to={to} end={end}>
              {() => (
                <motion.div
                  whileHover={{ x: 2 }}
                  transition={{ duration: 0.15 }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.75rem',
                    padding: '0.625rem 0.875rem',
                    borderRadius: 'var(--radius-md)',
                    background: active ? 'rgba(118,185,0,0.12)' : 'transparent',
                    color: active ? 'var(--accent)' : 'var(--text-secondary)',
                    fontSize: '0.875rem',
                    fontWeight: active ? 600 : 400,
                    transition: 'all var(--transition-fast)',
                    textDecoration: 'none',
                    position: 'relative',
                  }}
                >
                  {active && (
                    <motion.div
                      layoutId="sidebar-active"
                      style={{
                        position: 'absolute',
                        left: 0,
                        top: '20%',
                        bottom: '20%',
                        width: 3,
                        background: 'var(--accent)',
                        borderRadius: '0 2px 2px 0',
                      }}
                      transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                    />
                  )}
                  <Icon size={18} strokeWidth={active ? 2.5 : 1.8} />
                  {label}
                  {active && (
                    <ChevronRight size={14} style={{ marginLeft: 'auto', opacity: 0.5 }} />
                  )}
                </motion.div>
              )}
            </NavLink>
          )
        })}
      </nav>

      {/* System status */}
      <div
        style={{
          padding: '0.75rem 1rem',
          margin: '0 0.75rem',
          marginBottom: '0.5rem',
          background: 'var(--bg-surface-2)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-subtle)',
        }}
      >
        <div className="flex items-center gap-2">
          <Activity size={12} style={{ color: 'var(--accent)' }} />
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Sistema
          </span>
        </div>
        <div className="flex items-center gap-1 mt-1">
          <span
            style={{
              width: 6, height: 6, borderRadius: '50%',
              background: systemStatus === 'ready' ? 'var(--status-success)' : systemStatus === 'offline' ? 'var(--status-error)' : 'var(--status-warning)',
              boxShadow: systemStatus === 'ready' ? '0 0 6px var(--status-success)' : 'none',
              display: 'inline-block',
            }}
            className="animate-pulse-glow"
          />
          <span style={{ fontSize: '0.75rem', color: systemStatus === 'ready' ? 'var(--status-success)' : systemStatus === 'offline' ? 'var(--status-error)' : 'var(--status-warning)' }}>
            {systemStatus === 'ready' ? 'Pronto' : systemStatus === 'degraded' ? 'Degradado' : systemStatus === 'offline' ? 'Indisponivel' : 'Verificando'}
          </span>
        </div>
      </div>

      {/* User */}
      {user && (
        <div
          style={{
            padding: '1rem',
            borderTop: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <div
            style={{
              width: 32, height: 32, borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent-dim) 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
              fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-inverse)',
            }}
          >
            {user.email?.charAt(0).toUpperCase()}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="truncate" style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              {user.email}
            </div>
            <div style={{ fontSize: '0.65rem', color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              {role}
            </div>
          </div>
          <button
            onClick={signOut}
            className="btn btn-ghost btn-icon"
            title="Sair"
            style={{ padding: '0.35rem', flexShrink: 0 }}
          >
            <LogOut size={15} />
          </button>
        </div>
      )}
    </aside>
  )
}
