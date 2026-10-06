// Thin wrapper around fetch() that every page uses to talk to FastAPI.
// It attaches the JWT, turns FastAPI error payloads into readable messages,
// and tells AuthContext when the token is no longer accepted (401).

const BASE_URL = import.meta.env.VITE_API_URL || '/api'

let authToken = null
let onUnauthorized = () => {}

export function setAuthToken(token) {
  authToken = token
}

export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

// FastAPI errors look like {detail: "text"} or, for Pydantic 422s,
// {detail: [{loc: ["body", "fuel_level"], msg: "Input should be ..."}]}
function errorMessage(payload, status) {
  const detail = payload?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => `${d.loc?.filter((p) => p !== 'body').join('.') || 'request'}: ${d.msg}`)
      .join('; ')
  }
  return `Request failed (${status})`
}

async function request(path, { method = 'GET', body, formData, query } = {}) {
  const url = new URL(BASE_URL + path, window.location.origin)
  Object.entries(query || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
  })

  const headers = {}
  if (authToken) headers.Authorization = `Bearer ${authToken}`
  let payload
  if (formData) {
    payload = formData // browser sets the multipart boundary header itself
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  const res = await fetch(url, { method, headers, body: payload })
  if (res.status === 401 && authToken) onUnauthorized()
  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(errorMessage(data, res.status), res.status)
  return data
}

export const api = {
  get: (path, query) => request(path, { query }),
  post: (path, body) => request(path, { method: 'POST', body }),
  patch: (path, body) => request(path, { method: 'PATCH', body }),
  del: (path) => request(path, { method: 'DELETE' }),
  upload: (path, formData) => request(path, { method: 'POST', formData }),

  // OAuth2 password flow expects form fields, not JSON.
  login: async (email, password) => {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username: email, password }),
    })
    const data = await res.json().catch(() => null)
    if (!res.ok) throw new ApiError(errorMessage(data, res.status), res.status)
    return data
  },
}
