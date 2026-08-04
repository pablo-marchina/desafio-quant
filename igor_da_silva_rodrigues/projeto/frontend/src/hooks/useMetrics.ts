import { useState, useEffect } from 'react'
import { getMetrics } from '@/lib/api'
import type { ApiMetrics } from '@/types/api'

export function useMetrics(pollInterval = 0) {
  const [metrics, setMetrics] = useState<ApiMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = async () => {
    setError(null)
    try {
      const data = await getMetrics()
      setMetrics(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao buscar métricas')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetch()
    if (!pollInterval) return
    const interval = setInterval(fetch, pollInterval)
    return () => clearInterval(interval)
  }, [pollInterval])

  return { metrics, loading, error, refetch: fetch }
}
