import axios from 'axios'

export const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

// Access token lives only in memory; the refresh token is an HttpOnly cookie the browser sends to /auth/*.
let accessToken = null
let onSessionExpired = () => {}

export const setAccessToken = (t) => { accessToken = t }
export const setSessionExpiredHandler = (fn) => { onSessionExpired = fn }

export const api = axios.create({ baseURL: API_BASE, withCredentials: true, timeout: 30000 })

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  return config
})

let refreshing = null
export function refreshSession() {
  // de-duplicate concurrent refreshes (several requests may 401 at once)
  refreshing ??= axios
    .post(`${API_BASE}/auth/refresh`, null, { withCredentials: true })
    .then((r) => { setAccessToken(r.data.access_token); return r.data })
    .finally(() => { refreshing = null })
  return refreshing
}

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const { config, response } = error
    const code = response?.data?.error?.code
    const retriable = response?.status === 401 && !config._retried && !config.url.includes('/auth/')
    if (retriable && ['token_expired', 'invalid_token', 'unauthorized'].includes(code)) {
      config._retried = true
      try {
        await refreshSession()
        return api(config)
      } catch {
        onSessionExpired()
      }
    } else if (response?.status === 401 && !config.url.includes('/auth/login')) {
      if (['token_revoked', 'inactive_account'].includes(code)) onSessionExpired()
    }
    return Promise.reject(error)
  },
)

export function errorMessage(err, fallback = 'Something went wrong') {
  const data = err?.response?.data
  if (data instanceof Blob) return fallback
  return data?.error?.message || data?.detail || err?.message || fallback
}

/** Download a protected file (adds the bearer token) and trigger a save dialog. */
export async function downloadFile(url, params, fallbackName = 'download') {
  const res = await api.get(url, { params, responseType: 'blob' })
  const cd = res.headers['content-disposition'] || ''
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd)
  const name = match ? decodeURIComponent(match[1]) : fallbackName
  const href = URL.createObjectURL(res.data)
  const a = Object.assign(document.createElement('a'), { href, download: name })
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(href), 1000)
}

/** Open a protected PDF in a new tab. */
export async function openFile(url) {
  const win = window.open('', '_blank')
  const res = await api.get(url, { responseType: 'blob' })
  const href = URL.createObjectURL(res.data)
  if (win) win.location.href = href
  else window.location.href = href
}
