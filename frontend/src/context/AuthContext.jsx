import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setTok] = useState(() => getToken())
  const [username, setUsername] = useState(null)

  useEffect(() => {
    if (!token) {
      setUsername(null)
      return
    }
    // Decode payload locally to get username + exp without a round-trip.
    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      if (payload.exp && payload.exp * 1000 < Date.now()) {
        setToken(null)
        setTok(null)
        return
      }
      setUsername(payload.username || 'admin')
    } catch {
      setToken(null)
      setTok(null)
    }
  }, [token])

  const login = useCallback(async (username, password) => {
    const data = await api('/admin/login', { method: 'POST', body: { username, password } })
    setToken(data.token)
    setTok(data.token)
    setUsername(data.username)
    return data
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setTok(null)
    setUsername(null)
  }, [])

  return (
    <AuthContext.Provider value={{ token, username, isAuthed: !!token, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const v = useContext(AuthContext)
  if (!v) throw new Error('useAuth must be used inside AuthProvider')
  return v
}
