import { accessToken, clearSession, refreshSession } from './session'

export type Job = {
  id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | string
  progress: number
  result: {
    analysis_id?: string
    lead_ids?: string[]
    imported?: number
    failed?: number
    total?: number
  } | null
  error: { message: string } | null
}

export type Rate = { code: string; value: string | null; target: string; north_star?: boolean }

export type Metrics = {
  window_days: number
  rates: Record<string, Rate>
  timings_p50_seconds: Record<string, number | null>
  timing_targets_seconds: Record<string, number>
  redlines: { delivery_rate: string | null; bounce_rate: string | null; complaint_rate: string | null; tripped: boolean }
  alerts: { act_or_rec_p95_over_72h: boolean }
  import_success_rate: string | null
  counts: { analyses: number; acquired: number; leads: number; audience: number; delivered_people: number }
}

export function percent(value: string | null | undefined) {
  if (value == null || value === '') return '—'
  return `${(Number(value) * 100).toFixed(1)}%`
}

export function duration(value: number | null | undefined) {
  if (value == null) return '—'
  if (value < 90) return `${value.toFixed(1)} 秒`
  if (value < 3600) return `${Math.round(value / 60)} 分钟`
  if (value < 86400) return `${(value / 3600).toFixed(1)} 小时`
  return `${(value / 86400).toFixed(1)} 天`
}

function redirectLogin() {
  if (typeof window === 'undefined') return
  const path = window.location.pathname
  if (path === '/' || path.startsWith('/login') || path.startsWith('/register') || path.startsWith('/forgot') || path.startsWith('/reset') || path.startsWith('/admin')) return
  const next = `${path}${window.location.search}`
  window.location.assign(`/login?next=${encodeURIComponent(next)}`)
}

async function request<T>(path: string, init: RequestInit | undefined, allowRefresh: boolean): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const token = accessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`/api/v1${path}`, { ...init, headers, cache: 'no-store' })
  if (response.status === 401 && allowRefresh && token) {
    const refreshed = await refreshSession()
    if (refreshed) return request<T>(path, init, false)
    clearSession()
    redirectLogin()
  }
  if (response.status === 401 && !path.startsWith('/auth/')) {
    clearSession()
    redirectLogin()
  }
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body?.error?.message || '请求失败')
  return body.data as T
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  return request<T>(path, init, true)
}

export async function waitJob(jobId: string) {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const job = await api<Job>(`/jobs/${jobId}`)
    if (job.status === 'succeeded' || job.status === 'failed') return job
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  throw new Error('任务仍在排队，请稍后刷新')
}
