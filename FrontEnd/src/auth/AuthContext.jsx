import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, refreshSession, setAccessToken, setSessionExpiredHandler } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const qc = useQueryClient()

  const clear = useCallback(() => {
    setAccessToken(null)
    setUser(null)
    qc.clear()
  }, [qc])

  // restore the session from the refresh cookie on first load
  useEffect(() => {
    setSessionExpiredHandler(clear)
    refreshSession()
      .then((data) => setUser(data.user))
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [clear])

  const login = useCallback(async (email, password) => {
    const { data } = await api.post('/auth/login', { email, password })
    setAccessToken(data.access_token)
    setUser(data.user)
    return data.user
  }, [])

  const logout = useCallback(async () => {
    try { await api.post('/auth/logout') } catch { /* already signed out */ }
    clear()
  }, [clear])

  const applyTokenResponse = useCallback((data) => {
    setAccessToken(data.access_token)
    setUser(data.user)
  }, [])

  const value = useMemo(() => {
    const perms = new Set(user?.permissions || [])
    return {
      user,
      loading,
      login,
      logout,
      applyTokenResponse,
      can: (...codes) => codes.every((c) => perms.has(c)),
      canAny: (...codes) => codes.some((c) => perms.has(c)),
      hasEmployee: !!user?.employee,
    }
  }, [user, loading, login, logout, applyTokenResponse])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
