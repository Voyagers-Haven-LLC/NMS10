import { createContext, useCallback, useContext, useState } from 'react'

const ToastContext = createContext(null)

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => {
    setToasts((cur) => cur.filter((t) => t.id !== id))
  }, [])

  const push = useCallback((msg, kind = 'info', ttl = 4000) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
    setToasts((cur) => [...cur, { id, msg, kind }])
    setTimeout(() => dismiss(id), ttl)
  }, [dismiss])

  const value = {
    push,
    success: (m) => push(m, 'success'),
    error: (m) => push(m, 'error', 6000),
    info: (m) => push(m, 'info'),
  }

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-container">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`} onClick={() => dismiss(t.id)}>
            {t.msg}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const v = useContext(ToastContext)
  if (!v) throw new Error('useToast must be used inside ToastProvider')
  return v
}
