const KEY = 'pickglobal.session'

export type SessionTokens = {
  access_token: string
  refresh_token: string
  expires_in?: number
}

type Stored = SessionTokens

export function readSession(): Stored | null {
  if (typeof window === 'undefined') return null
  const raw = localStorage.getItem(KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Stored
    if (!parsed.access_token || !parsed.refresh_token) return null
    return parsed
  } catch {
    return null
  }
}

export function accessToken() {
  return readSession()?.access_token || ''
}

export function writeSession(tokens: SessionTokens) {
  localStorage.setItem(KEY, JSON.stringify({ access_token: tokens.access_token, refresh_token: tokens.refresh_token }))
}

export function clearSession() {
  localStorage.removeItem(KEY)
}

export function safeNext(value: string | null) {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.startsWith('/login')) return '/workspace'
  return value
}

export function accountBody(account: string) {
  const value = account.trim()
  if (value.includes('@')) return { email: value.replace(/\s/g, '').toLowerCase() }
  const compact = value.replace(/[\s-]/g, '')
  if (/^\+?\d{6,}$/.test(compact)) return { phone: compact }
  return { username: value }
}

const COLD_START = '服务正在启动，请再点一次登录（大约半分钟）'
const AUTH_TIMEOUT_MS = 25000
const AUTH_RETRIES = 3

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function isCold(status: number, body: unknown) {
  if (status === 502 || status === 503 || status === 504) return true
  const text = typeof body === 'string' ? body : JSON.stringify(body || {})
  return /temporarily unavailable|scaleActiveing|cold/i.test(text)
}

async function authFetch(path: string, init?: RequestInit) {
  let last: Error = new Error(COLD_START)
  for (let attempt = 0; attempt < AUTH_RETRIES; attempt += 1) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), AUTH_TIMEOUT_MS)
    try {
      const response = await fetch(path, { ...init, signal: controller.signal, cache: 'no-store' })
      const raw = await response.text()
      let body: { data?: unknown; error?: { message?: string } } = {}
      try {
        body = raw ? JSON.parse(raw) : {}
      } catch {
        body = {}
      }
      if (isCold(response.status, raw)) {
        last = new Error(COLD_START)
        if (attempt < AUTH_RETRIES - 1) await sleep(4000)
        continue
      }
      if (!response.ok) throw new Error(body?.error?.message || '请求失败')
      return body.data
    } catch (reason) {
      if (reason instanceof Error && reason.message && reason.message !== COLD_START && reason.name !== 'AbortError') {
        throw reason
      }
      last = new Error(COLD_START)
      if (attempt < AUTH_RETRIES - 1) await sleep(4000)
    } finally {
      clearTimeout(timer)
    }
  }
  throw last
}

export async function loginAccount(account: string, password: string, recall?: string) {
  const data = (await authFetch('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...accountBody(account), password, recall: recall || undefined }),
  })) as SessionTokens
  writeSession(data)
  return data
}

export async function registerAccount(input: { account: string; password: string; displayName: string; code?: string; inviteCode?: string }) {
  await authFetch('/api/v1/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...accountBody(input.account),
      password: input.password,
      display_name: input.displayName || null,
      code: input.code || null,
      invite_code: input.inviteCode || null,
    }),
  })
  return loginAccount(input.account, input.password)
}

export async function forgotAccount(account: string) {
  return (await authFetch('/api/v1/auth/forgot-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(accountBody(account)),
  })) as { accepted: boolean; reset_token?: string; channel?: string; sms_sent_today?: number; sms_daily_cap?: number; sms_quota_warning?: boolean }
}

export async function resetWithSms(phone: string, code: string, password: string) {
  return (await authFetch('/api/v1/auth/reset-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, code, password }),
  })) as { reset: boolean }
}

export async function resetAccount(token: string, password: string) {
  return (await authFetch('/api/v1/auth/reset-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, password }),
  })) as { reset: boolean }
}

export async function sendLoginCode(account: string, purpose: 'login' | 'register' | 'reset_password' = 'login') {
  return (await authFetch('/api/v1/auth/code/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...accountBody(account), purpose }),
  })) as { sent: boolean; code?: string; channel?: string; purpose?: string; sms_sent_today?: number; sms_daily_cap?: number; sms_quota_warning?: boolean }
}

export async function wechatAuthorizeUrl() {
  return (await authFetch('/api/v1/auth/wechat/authorize')) as { url: string }
}

export async function completeWechatLogin(code: string, state: string) {
  const data = (await authFetch('/api/v1/auth/oauth/wechat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, state }),
  })) as SessionTokens
  writeSession(data)
  return data
}

export async function loginWithCode(account: string, code: string, recall?: string) {
  const data = (await authFetch('/api/v1/auth/code/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...accountBody(account), code, recall: recall || undefined }),
  })) as SessionTokens
  writeSession(data)
  return data
}

export async function refreshSession() {
  const current = readSession()
  if (!current) return false
  const response = await fetch('/api/v1/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: current.refresh_token }),
  })
  if (!response.ok) return false
  const body = await response.json().catch(() => ({}))
  if (!body?.data?.access_token) return false
  writeSession(body.data as SessionTokens)
  return true
}

export async function logoutSession() {
  const token = accessToken()
  clearSession()
  if (!token) return
  await fetch('/api/v1/auth/logout', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  }).catch(() => undefined)
}
