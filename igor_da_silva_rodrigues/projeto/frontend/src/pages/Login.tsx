import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { NvidiaLogo } from '@/components/ui/NvidiaLogo'
import { Button } from '@/components/ui/Button'
import { useAuthStore } from '@/store/authStore'
import { Zap, Shield, Brain } from 'lucide-react'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const { signIn, loading } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
      setError('Informe um e-mail valido.')
      return
    }
    if (password.length < 6) {
      setError('A senha deve ter pelo menos 6 caracteres.')
      return
    }
    try {
      await signIn(email, password)
      navigate('/')
    } catch (err) {
      setError(localizeAuthError(err))
    }
  }

  const features = [
    { icon: <Brain size={20} />, label: 'Análise AI-native' },
    { icon: <Shield size={20} />, label: 'RBAC & JWT Supabase' },
    { icon: <Zap size={20} />, label: 'Pipeline de 9 agentes' },
  ]

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem',
        background: 'var(--bg-base)',
      }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.97, y: 24 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        style={{ width: '100%', maxWidth: 440, position: 'relative', zIndex: 1 }}
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.875rem', marginBottom: '1rem' }}>
            <NvidiaLogo size={44} />
            <div style={{ textAlign: 'left' }}>
              <div
                style={{
                  fontFamily: 'var(--font-heading)',
                  fontSize: '1.5rem',
                  fontWeight: 700,
                  color: 'var(--text-primary)',
                  lineHeight: 1.1,
                }}
              >
                AI Radar
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--accent)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                NVIDIA Inception Intelligence
              </div>
            </div>
          </div>
          <p className="text-muted text-sm">
            Plataforma de análise de startups AI-native brasileiras
          </p>
        </div>

        {/* Form card */}
        <div
          className="glass"
          style={{ padding: '2rem' }}
        >
          <h2 style={{ marginBottom: '1.5rem', fontSize: '1.1rem' }}>Entrar na plataforma</h2>

          <form onSubmit={handleSubmit} noValidate>
            <div style={{ marginBottom: '1rem' }}>
              <label htmlFor="email">E-mail</label>
              <input
                id="email"
                type="email"
                className="input"
                placeholder="seu@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <label htmlFor="password">Senha</label>
              <input
                id="password"
                type="password"
                className="input"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                style={{
                  background: 'rgba(232,64,64,0.1)',
                  border: '1px solid rgba(232,64,64,0.3)',
                  borderRadius: 'var(--radius-md)',
                  padding: '0.625rem 1rem',
                  color: 'var(--status-error)',
                  fontSize: '0.85rem',
                  marginBottom: '1rem',
                }}
              >
                {error}
              </motion.div>
            )}

            <Button
              type="submit"
              variant="primary"
              className="w-full"
              loading={loading}
              style={{ width: '100%', justifyContent: 'center', padding: '0.75rem' }}
            >
              Entrar
            </Button>
          </form>
        </div>

        {/* Features */}
        <div className="flex justify-center gap-6 mt-6">
          {features.map((f) => (
            <div key={f.label} className="flex flex-col items-center gap-1" style={{ opacity: 0.6 }}>
              <span style={{ color: 'var(--accent)' }}>{f.icon}</span>
              <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textAlign: 'center' }}>
                {f.label}
              </span>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}

function localizeAuthError(error: unknown): string {
  const message = error instanceof Error ? error.message.toLowerCase() : ''
  if (message.includes('invalid login credentials')) return 'E-mail ou senha incorretos.'
  if (message.includes('email not confirmed')) return 'Confirme seu e-mail antes de entrar.'
  if (message.includes('failed to fetch') || message.includes('network')) return 'Nao foi possivel conectar ao servico de autenticacao.'
  if (message.includes('rate limit')) return 'Muitas tentativas. Aguarde um momento e tente novamente.'
  return 'Nao foi possivel entrar. Verifique os dados e tente novamente.'
}
