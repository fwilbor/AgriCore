// Global authentication state via the React Context API.
//
// <AuthProvider> wraps the whole app (see main.jsx). Any component can call
// useAuth() to read the logged-in user or call login()/logout() - no prop
// drilling through every layer of the component tree.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, setAuthToken, setUnauthorizedHandler } from '../api/client'

const AuthContext = createContext(null)
const TOKEN_KEY = 'agricore_token'
const USER_KEY = 'agricore_user'

function readStorage(key) {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => readStorage(TOKEN_KEY))
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(readStorage(USER_KEY) || 'null')
    } catch {
      return null
    }
  })

  // Keep the API client's token in sync during render, so child components'
  // first requests already carry the Authorization header.
  setAuthToken(token)

  const logout = useCallback(() => {
    try {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
    } catch {
      /* storage unavailable - nothing to clear */
    }
    setToken(null)
    setUser(null)
  }, [])

  const login = useCallback(async (email, password) => {
    const data = await api.login(email, password)
    try {
      localStorage.setItem(TOKEN_KEY, data.access_token)
      localStorage.setItem(USER_KEY, JSON.stringify(data.user))
    } catch {
      /* private mode - session lasts until refresh */
    }
    setAuthToken(data.access_token)
    setToken(data.access_token)
    setUser(data.user)
    return data.user
  }, [])

  // Any 401 from the API (expired token) logs the user out.
  useEffect(() => setUnauthorizedHandler(logout), [logout])

  // On page load, confirm the stored token is still valid.
  useEffect(() => {
    if (token) api.get('/auth/me').then(setUser).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const value = useMemo(
    () => ({
      user,
      token,
      isAuthenticated: Boolean(token && user),
      login,
      logout,
      hasRole: (...roles) => Boolean(user && roles.includes(user.role)),
    }),
    [user, token, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}

export const ROLE_LABELS = {
  admin: 'Farm Operations Admin',
  farm_hand: 'Farm Hand',
  auditor: 'Auditor (Read-Only)',
}
