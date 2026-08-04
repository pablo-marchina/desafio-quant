import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'
import { supabase } from './supabase'
import type {
  Startup,
  RunAnalysis,
  Batch,
  BatchItem,
  DeadLetter,
  BatchCreateRequest,
  ApiMetrics,
  Evidence,
  POCBlueprint,
  StartupDiscoveryResult,
} from '@/types/api'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
const AUTH_MODE = import.meta.env.VITE_AUTH_MODE || 'supabase'
const DEV_API_KEY = import.meta.env.VITE_DEV_API_KEY as string | undefined

// ------------------------------------------------------------------
// Axios instance
// ------------------------------------------------------------------
const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
})

// Request interceptor: attach auth header
api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  if (AUTH_MODE === 'apikey' && DEV_API_KEY) {
    config.headers['X-API-Key'] = DEV_API_KEY
    return config
  }

  const {
    data: { session },
  } = await supabase.auth.getSession()

  if (session?.access_token) {
    config.headers['Authorization'] = `Bearer ${session.access_token}`
  }

  return config
})

// Response interceptor: refresh token on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      const { data } = await supabase.auth.refreshSession()
      if (data.session?.access_token) {
        originalRequest.headers['Authorization'] = `Bearer ${data.session.access_token}`
        return api(originalRequest)
      }
    }
    return Promise.reject(error)
  }
)

// ------------------------------------------------------------------
// API functions
// ------------------------------------------------------------------

// Health
export const getHealth = () => axios.get(`${BASE_URL}/health`).then((r) => r.data)
export const getReadiness = () => axios
  .get(`${BASE_URL}/ready`, { validateStatus: (status) => status === 200 || status === 503 })
  .then((response) => response.data as { status: 'ready' | 'degraded'; checks: Record<string, boolean> })

// Startups
export const listStartups = (limit = 50, offset = 0) =>
  api.get<Startup[]>('/api/v1/startups', { params: { limit, offset } }).then((r) => r.data)

export const getStartup = (id: string) =>
  api.get<Startup>(`/api/v1/startups/${id}`).then((r) => r.data)

export const discoverStartups = (limit: number, offset: number) =>
  api
    .post<StartupDiscoveryResult>('/api/v1/startups/discover', { limit, offset }, { timeout: 180_000 })
    .then((r) => r.data)

// Runs
export const getRunAnalysis = (runId: string) =>
  api.get<RunAnalysis>(`/api/v1/runs/${runId}`).then((r) => r.data)

export const getRunBriefing = (runId: string) =>
  api.get<string>(`/api/v1/runs/${runId}/briefing`, {
    headers: { Accept: 'text/markdown' },
    responseType: 'text',
  }).then((r) => r.data)

export const getRunEvidences = (runId: string) =>
  api.get<Evidence[]>(`/api/v1/runs/${runId}/evidences`).then((r) => r.data)

export const getPOCBlueprint = (runId: string) =>
  api.get<POCBlueprint>(`/api/v1/runs/${runId}/poc-blueprint`).then((r) => r.data)

// Batches
export const listBatches = (limit = 20) =>
  api.get<Batch[]>('/api/v1/batches', { params: { limit } }).then((r) => r.data)

export const getBatch = (id: string) =>
  api.get<Batch>(`/api/v1/batches/${id}`).then((r) => r.data)

export const getBatchItems = (id: string, status?: string) =>
  api
    .get<BatchItem[]>(`/api/v1/batches/${id}/items`, { params: status ? { status } : {} })
    .then((r) => r.data)

export const getDeadLetters = (batchId: string) =>
  api.get<DeadLetter[]>(`/api/v1/batches/${batchId}/dead-letters`).then((r) => r.data)

export const createBatch = (body: BatchCreateRequest) =>
  api.post<Batch>('/api/v1/batches', body).then((r) => r.data)

export const runBatch = (id: string) =>
  api.post<Batch>(`/api/v1/batches/${id}/run`).then((r) => r.data)

export const resumeBatch = (id: string, reprocessPartial = false) =>
  api
    .post<Batch>(`/api/v1/batches/${id}/resume`, null, {
      params: { reprocess_partial: reprocessPartial },
    })
    .then((r) => r.data)

export const cancelBatch = (id: string) =>
  api.post<Batch>(`/api/v1/batches/${id}/cancel`).then((r) => r.data)

export const replayDeadLetter = (deadLetterId: string) =>
  api.post(`/api/v1/batches/dead-letters/${deadLetterId}/replay`).then((r) => r.data)

// Metrics
export const getMetrics = () =>
  api.get<ApiMetrics>('/api/v1/metrics').then((r) => r.data)

export default api
