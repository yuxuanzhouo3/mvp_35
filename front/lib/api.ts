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

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  headers.set('Authorization', 'Bearer demo')
  const response = await fetch(`/api/v1${path}`, { ...init, headers, cache: 'no-store' })
  const body = await response.json()
  if (!response.ok) throw new Error(body?.error?.message || '请求失败')
  return body.data as T
}

export async function waitJob(jobId: string) {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const job = await api<Job>(`/jobs/${jobId}`)
    if (job.status === 'succeeded' || job.status === 'failed') return job
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  throw new Error('任务仍在排队，请稍后刷新')
}
