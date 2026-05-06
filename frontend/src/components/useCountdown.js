import { useEffect, useState } from 'react'

// Aug 9, 2026 18:00 UTC — locked target from the v9 mockup.
export const TARGET_TS = Date.UTC(2026, 7, 9, 18, 0, 0)

export function useCountdown() {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  const diff = TARGET_TS - now
  if (diff <= 0) {
    return { reached: true, days: 0, hours: 0, minutes: 0, seconds: 0 }
  }
  return {
    reached: false,
    days: Math.floor(diff / 86400000),
    hours: Math.floor((diff / 3600000) % 24),
    minutes: Math.floor((diff / 60000) % 60),
    seconds: Math.floor((diff / 1000) % 60),
  }
}

export function pad(n, w = 2) {
  return String(n).padStart(w, '0')
}
