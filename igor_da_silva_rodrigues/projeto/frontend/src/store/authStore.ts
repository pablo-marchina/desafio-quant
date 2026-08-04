import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User, Session } from '@/lib/supabase'
import { supabase } from '@/lib/supabase'

interface AuthState {
  user: User | null
  session: Session | null
  loading: boolean
  role: 'admin' | 'analyst' | 'readonly' | null
  setSession: (session: Session | null) => void
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  initialize: () => Promise<void>
}

let authListenerInitialized = false

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      session: null,
      loading: true,
      role: null,

      setSession: (session) => {
        const role = extractRole(session)
        set({ session, user: session?.user ?? null, role, loading: false })
      },

      signIn: async (email, password) => {
        set({ loading: true })
        const { data, error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) {
          set({ loading: false })
          throw error
        }
        const role = extractRole(data.session)
        set({ session: data.session, user: data.user, role, loading: false })
      },

      signOut: async () => {
        await supabase.auth.signOut()
        set({ session: null, user: null, role: null })
      },

      initialize: async () => {
        set({ loading: true })
        const {
          data: { session },
        } = await supabase.auth.getSession()
        const role = extractRole(session)
        set({ session, user: session?.user ?? null, role, loading: false })

        if (!authListenerInitialized) {
          authListenerInitialized = true
          supabase.auth.onAuthStateChange((_event, session) => {
            const role = extractRole(session)
            set({ session, user: session?.user ?? null, role })
          })
        }
      },
    }),
    {
      name: 'nvidia-radar-auth',
      partialize: (state) => ({ user: state.user, session: state.session, role: state.role }),
    }
  )
)

function extractRole(session: Session | null): 'admin' | 'analyst' | 'readonly' | null {
  if (!session) return null
  const claims = session.user?.app_metadata ?? {}
  const userRole = (claims.radar_role ?? claims.role) as string | undefined
  if (userRole === 'admin' || userRole === 'analyst' || userRole === 'readonly') return userRole
  return 'readonly'
}
