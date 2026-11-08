import { create } from 'zustand'

import {
  getCurrentUser,
  login as apiLogin,
  logout as apiLogout,
} from '../api/client'
import type { AuthUser } from '../api/types'

interface AuthState {
  user: AuthUser | null
  loading: boolean
  error: string | null
  login: (username: string, password: string) => Promise<boolean>
  logout: () => Promise<void>
  checkAuth: () => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: true,
  error: null,

  async login(username, password) {
    set({ loading: true, error: null })
    try {
      const response = await apiLogin(username, password)
      set({ user: response.user, loading: false, error: null })
      return true
    } catch (cause) {
      const text = cause instanceof Error ? cause.message : ''
      set({
        user: null,
        loading: false,
        error: text.includes('429') ? 'too_many_attempts' : 'invalid_credentials',
      })
      return false
    }
  },

  async logout() {
    try {
      await apiLogout()
    } finally {
      set({ user: null, loading: false, error: null })
    }
  },

  async checkAuth() {
    set({ loading: true })
    try {
      const user = await getCurrentUser()
      set({ user, loading: false })
    } catch {
      set({ user: null, loading: false })
    }
  },

  clearError() {
    set({ error: null })
  },
}))
