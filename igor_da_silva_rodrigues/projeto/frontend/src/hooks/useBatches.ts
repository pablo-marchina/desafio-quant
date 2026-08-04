import { useState, useEffect, useCallback } from 'react'
import {
  listBatches,
  getBatch,
  getBatchItems,
  getDeadLetters,
  createBatch,
  runBatch,
  resumeBatch,
  cancelBatch,
  replayDeadLetter,
} from '@/lib/api'
import type { Batch, BatchItem, DeadLetter, BatchCreateRequest } from '@/types/api'

export function useBatches(limit = 20) {
  const [batches, setBatches] = useState<Batch[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchBatches = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listBatches(limit)
      setBatches(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao buscar lotes')
    } finally {
      setLoading(false)
    }
  }, [limit])

  useEffect(() => {
    fetchBatches()
  }, [fetchBatches])

  return { batches, loading, error, refetch: fetchBatches }
}

export function useBatch(id: string | undefined, pollInterval = 0) {
  const [batch, setBatch] = useState<Batch | null>(null)
  const [items, setItems] = useState<BatchItem[]>([])
  const [deadLetters, setDeadLetters] = useState<DeadLetter[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [acting, setActing] = useState(false)
  const batchStatus = batch?.status

  const fetchAll = useCallback(async () => {
    if (!id) return
    setError(null)
    try {
      const [batchData, itemsData, dlData] = await Promise.all([
        getBatch(id),
        getBatchItems(id),
        getDeadLetters(id),
      ])
      setBatch(batchData)
      setItems(itemsData)
      setDeadLetters(dlData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao buscar lote')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    fetchAll()
    const active = !batchStatus || batchStatus === 'pending' || batchStatus === 'running'
    if (!pollInterval || !active) return
    const interval = setInterval(fetchAll, pollInterval)
    return () => clearInterval(interval)
  }, [batchStatus, fetchAll, pollInterval])

  const act = async (fn: () => Promise<unknown>) => {
    setActing(true)
    try {
      await fn()
      await fetchAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Nao foi possivel executar a acao')
    } finally {
      setActing(false)
    }
  }

  const handleRun = () => id && act(() => runBatch(id))
  const handleResume = (reprocess = false) => id && act(() => resumeBatch(id, reprocess))
  const handleCancel = () => id && act(() => cancelBatch(id))
  const handleReplay = (dlId: string) => act(() => replayDeadLetter(dlId))

  return {
    batch,
    items,
    deadLetters,
    loading,
    error,
    acting,
    refetch: fetchAll,
    handleRun,
    handleResume,
    handleCancel,
    handleReplay,
  }
}

export function useCreateBatch() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const create = async (body: BatchCreateRequest): Promise<Batch | null> => {
    setLoading(true)
    setError(null)
    try {
      const data = await createBatch(body)
      return data
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar lote')
      return null
    } finally {
      setLoading(false)
    }
  }

  return { create, loading, error }
}
