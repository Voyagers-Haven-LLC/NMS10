import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'

export default function AdminLogin() {
  const { login } = useAuth()
  const toast = useToast()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(username, password)
      toast.success('Logged in.')
    } catch (err) {
      setError(err.message || 'Invalid credentials')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="container">
      <div className="login-card">
        <h1>Admin login</h1>
        <p className="login-meta">Voyager's Haven moderation</p>
        <form onSubmit={submit}>
          <div className="form-grid single">
            <div className="form-field">
              <label>Username</label>
              <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
            </div>
            <div className="form-field">
              <label>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && (
              <div style={{ color: '#ff8a8a', fontSize: '0.85rem' }}>{error}</div>
            )}
          </div>
          <div className="form-actions">
            <button type="submit" className="btn primary" disabled={busy}>
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
