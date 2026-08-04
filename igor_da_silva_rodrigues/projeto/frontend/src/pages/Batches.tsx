import { useState } from 'react'
import { motion } from 'framer-motion'
import { Plus, RefreshCw } from 'lucide-react'
import { BatchCard } from '@/components/batch/BatchCard'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { useBatches, useCreateBatch } from '@/hooks/useBatches'
import { runBatch, resumeBatch, cancelBatch } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'

export default function Batches() {
  const { batches, loading, error, refetch } = useBatches(30)
  const { create, loading: creating, error: createError } = useCreateBatch()
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ limit: '', max_attempts: '2', stop_on_error: false })
  const [acting, setActing] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const role = useAuthStore((state) => state.role)
  const canManage = role === 'admin' || role === 'analyst'

  const handleCreate = async () => {
    const body = {
      limit: form.limit ? Number(form.limit) : undefined,
      max_attempts: Number(form.max_attempts),
      stop_on_error: form.stop_on_error,
      include_ineligible: true,
    }
    const batch = await create(body)
    if (batch) {
      setShowModal(false)
      refetch()
    }
  }

  const act = async (fn: () => Promise<unknown>) => {
    setActing(true)
    setActionError(null)
    try {
      await fn()
    } catch (requestError) {
      setActionError(requestError instanceof Error ? requestError.message : 'Nao foi possivel executar a acao.')
    } finally {
      setActing(false)
      refetch()
    }
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
      {/* Toolbar */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            {batches.length} lote{batches.length !== 1 ? 's' : ''}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" icon={<RefreshCw size={14} />} onClick={refetch} loading={loading}>
            Atualizar
          </Button>
          {canManage && <Button variant="primary" size="sm" icon={<Plus size={14} />} onClick={() => setShowModal(true)}>
            Novo Lote
          </Button>}
        </div>
      </div>
      {actionError && <p className="text-error text-sm mb-3">{actionError}</p>}

      {loading ? (
        <div className="empty-state" style={{ minHeight: 300 }}>
          <Spinner size="lg" />
          <p>Carregando lotes…</p>
        </div>
      ) : error ? (
        <div className="empty-state">
          <p className="text-error">{error}</p>
          <Button onClick={refetch} variant="secondary">Tentar novamente</Button>
        </div>
      ) : batches.length === 0 ? (
        <div className="empty-state">
          <p>Nenhum lote encontrado. Crie o primeiro!</p>
          {canManage && <Button variant="primary" icon={<Plus size={14} />} onClick={() => setShowModal(true)}>
            Criar Lote
          </Button>}
        </div>
      ) : (
        <motion.div
          className="grid grid-2"
          style={{ gap: '1rem' }}
          initial="hidden"
          animate="show"
          variants={{ hidden: {}, show: { transition: { staggerChildren: 0.06 } } }}
        >
          {batches.map((batch) => (
            <motion.div
              key={batch.id}
              variants={{ hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0 } }}
            >
              <BatchCard
                batch={batch}
                onRun={canManage ? (id) => act(() => runBatch(id)) : undefined}
                onResume={canManage ? (id) => act(() => resumeBatch(id)) : undefined}
                onCancel={role === 'admin' ? (id) => act(() => cancelBatch(id)) : undefined}
                acting={acting}
              />
            </motion.div>
          ))}
        </motion.div>
      )}

      {/* Create modal */}
      {showModal && canManage && (
        <div className="overlay" onClick={() => setShowModal(false)}>
          <motion.div
            className="modal"
            initial={{ opacity: 0, scale: 0.95, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 style={{ marginBottom: '1.5rem', fontSize: '1.1rem' }}>Criar Novo Lote</h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '1.5rem' }}>
              <div>
                <label htmlFor="batch-limit">Limite de Startups (deixe vazio para todas)</label>
                <input
                  id="batch-limit"
                  type="number"
                  className="input"
                  min={1}
                  max={50}
                  placeholder="Ex: 10"
                  value={form.limit}
                  onChange={(e) => setForm((f) => ({ ...f, limit: e.target.value }))}
                />
              </div>

              <div>
                <label htmlFor="batch-max-attempts">Máx. de Tentativas por Startup</label>
                <select
                  id="batch-max-attempts"
                  className="input"
                  value={form.max_attempts}
                  onChange={(e) => setForm((f) => ({ ...f, max_attempts: e.target.value }))}
                >
                  <option value="1">1</option>
                  <option value="2">2</option>
                  <option value="3">3</option>
                </select>
              </div>

              <label style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer', marginBottom: 0 }}>
                <input
                  type="checkbox"
                  id="batch-stop-on-error"
                  checked={form.stop_on_error}
                  onChange={(e) => setForm((f) => ({ ...f, stop_on_error: e.target.checked }))}
                  style={{ accentColor: 'var(--accent)', width: 16, height: 16 }}
                />
                Parar ao encontrar erro
              </label>
            </div>

            <div className="flex gap-2 justify-between">
              <Button variant="ghost" onClick={() => setShowModal(false)}>Cancelar</Button>
              <Button variant="primary" onClick={handleCreate} loading={creating}>
                Criar e Salvar
              </Button>
            </div>
            {createError && <p className="text-error text-sm mt-3">{createError}</p>}
          </motion.div>
        </div>
      )}
    </motion.div>
  )
}
