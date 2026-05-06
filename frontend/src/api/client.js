// Tiny fetch wrapper around the FastAPI backend.
//
// All non-admin reads/writes go through `api()`. Admin calls use `apiAuth()`,
// which adds the JWT from localStorage. Errors throw with the body's `detail`
// when present, so callers can surface a useful message.

const TOKEN_KEY = 'nms10_admin_token'

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}
export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {}
}

async function parseError(res) {
  let detail = `${res.status} ${res.statusText}`
  try {
    const body = await res.json()
    if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
  } catch {}
  const err = new Error(detail)
  err.status = res.status
  return err
}

export async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) }
  if (opts.body && !(opts.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  const body =
    opts.body instanceof FormData || typeof opts.body === 'string' || opts.body === undefined
      ? opts.body
      : JSON.stringify(opts.body)
  const res = await fetch(`/api${path}`, { ...opts, headers, body })
  if (!res.ok) throw await parseError(res)
  if (res.status === 204) return null
  const ctype = res.headers.get('content-type') || ''
  if (ctype.includes('application/json')) return res.json()
  return res.text()
}

export async function apiAuth(path, opts = {}) {
  const token = getToken()
  const headers = { ...(opts.headers || {}) }
  if (token) headers.Authorization = `Bearer ${token}`
  return api(path, { ...opts, headers })
}
