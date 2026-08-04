import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Spinner } from '@/components/ui/Spinner'
import { useAuthStore } from '@/store/authStore'
const Batches = lazy(() => import('@/pages/Batches'))
const BatchDetailPage = lazy(() => import('@/pages/BatchDetailPage'))
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const Login = lazy(() => import('@/pages/Login'))
const StartupPage = lazy(() => import('@/pages/StartupPage'))
const Startups = lazy(() => import('@/pages/Startups'))

const localApiKeyMode =
  import.meta.env.DEV &&
  import.meta.env.VITE_AUTH_MODE === 'apikey' &&
  Boolean(import.meta.env.VITE_DEV_API_KEY)

function LoadingScreen() {
  return (
    <div
      role="status"
      aria-label="Carregando sessão"
      style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}
    >
      <Spinner size="lg" />
    </div>
  )
}

function ProtectedLayout() {
  const { session, loading } = useAuthStore()
  if (loading) return <LoadingScreen />
  if (!session && !localApiKeyMode) return <Navigate to="/login" replace />
  return <AppShell />
}

function LoginRoute() {
  const { session, loading } = useAuthStore()
  if (loading) return <LoadingScreen />
  if (session || localApiKeyMode) return <Navigate to="/" replace />
  return <Login />
}

export default function App() {
  const initialize = useAuthStore((state) => state.initialize)

  useEffect(() => {
    void initialize()
  }, [initialize])

  return (
    <BrowserRouter>
      <Suspense fallback={<LoadingScreen />}><Routes>
        <Route path="/login" element={<LoginRoute />} />
        <Route element={<ProtectedLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="startups" element={<Startups />} />
          <Route path="startups/:id" element={<StartupPage />} />
          <Route path="batches" element={<Batches />} />
          <Route path="batches/:id" element={<BatchDetailPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes></Suspense>
    </BrowserRouter>
  )
}
