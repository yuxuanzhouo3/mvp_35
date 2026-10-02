const TOKEN_KEY = 'pickglobal.admin.token'

export type AdminSession = {
  user: { id: string; display_name: string; username?: string | null; role?: string }
  role: string
}

export function adminToken() {
  if (typeof window === 'undefined') return ''
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setAdminToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearAdminToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export async function adminApi<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const token = adminToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`/api/v1${path}`, { ...init, headers, cache: 'no-store' })
  const body = await response.json().catch(() => ({}))
  if (response.status === 401 && !path.startsWith('/auth/login')) {
    clearAdminToken()
    if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/admin/login')) {
      window.location.assign('/admin/login')
    }
  }
  if (!response.ok) throw new Error(body?.error?.message || '请求失败')
  return body.data as T
}

export async function adminLogin(username: string, password: string) {
  const response = await fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body?.error?.message || '登录失败')
  setAdminToken(body.data.access_token as string)
  return body.data as { access_token: string }
}

export function downloadText(filename: string, body: string, type = 'text/csv;charset=utf-8') {
  const blob = new Blob([body], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
