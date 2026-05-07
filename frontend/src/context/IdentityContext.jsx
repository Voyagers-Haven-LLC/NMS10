import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { getIdentity, saveIdentity as storageSave, clearIdentity as storageClear } from '../identity/identityStorage'

const IdentityContext = createContext(null)

const IDENTITY_EVENT = 'nms10:identity-changed'

export function IdentityProvider({ children }) {
  // Hydrate from localStorage on first render. Children rendered immediately
  // see the persisted value; no flicker.
  const [identity, setIdentityState] = useState(() => getIdentity())

  // Listen for cross-component update events. Useful if the user opens the
  // submit-base modal in one place, then opens the identity modal from the
  // header without closing the first — the form re-pulls fresh values.
  useEffect(() => {
    const onChange = () => setIdentityState(getIdentity())
    window.addEventListener(IDENTITY_EVENT, onChange)
    // Also pick up changes from a different tab (storage event)
    const onStorage = (e) => {
      if (e.key && e.key.startsWith('nms10_traveler_identity')) {
        setIdentityState(getIdentity())
      }
    }
    window.addEventListener('storage', onStorage)
    return () => {
      window.removeEventListener(IDENTITY_EVENT, onChange)
      window.removeEventListener('storage', onStorage)
    }
  }, [])

  const setIdentity = useCallback((draft) => {
    const saved = storageSave(draft)
    setIdentityState(saved)
    window.dispatchEvent(new CustomEvent(IDENTITY_EVENT, { detail: saved }))
    return saved
  }, [])

  const clearIdentity = useCallback(() => {
    storageClear()
    setIdentityState(null)
    window.dispatchEvent(new CustomEvent(IDENTITY_EVENT, { detail: null }))
  }, [])

  const value = {
    identity,
    hasIdentity: !!identity,
    setIdentity,
    clearIdentity,
  }

  return <IdentityContext.Provider value={value}>{children}</IdentityContext.Provider>
}

export function useIdentity() {
  const v = useContext(IdentityContext)
  if (!v) throw new Error('useIdentity must be used inside IdentityProvider')
  return v
}
