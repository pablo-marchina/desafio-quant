import { useState, useEffect, useCallback } from 'react'
import { listStartups, getStartup } from '@/lib/api'
import type { Startup } from '@/types/api'

export function useStartups(limit = 50, offset = 0) {
  const [startups, setStartups] = useState<Startup[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStartups = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listStartups(limit, offset)
      setStartups(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao buscar startups')
    } finally {
      setLoading(false)
    }
  }, [limit, offset])

  useEffect(() => {
    fetchStartups()
  }, [fetchStartups])

  return { startups, loading, error, refetch: fetchStartups }
}

export function useStartup(id: string | undefined) {
  const [startup, setStartup] = useState<Startup | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setError(null)
    getStartup(id)
      .then(setStartup)
      .catch((err) => setError(err instanceof Error ? err.message : 'Erro ao buscar startup'))
      .finally(() => setLoading(false))
  }, [id])

  return { startup, loading, error }
}
