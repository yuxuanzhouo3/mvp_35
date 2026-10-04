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

async function readError(response: Response) {
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body?.error?.message || '请求失败')
  return body.data
}

export async function loginAccount(account: string, password: string, recall?: string) {
  const response = await fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...accountBody(account), password, recall: recall || undefined }),
  })
  const data = (await readError(response)) as SessionTokens
  writeSession(data)
  return data
}

export async function registerAccount(input: { account: string; password: string; displayName: string; code?: string; inviteCode?: string }) {
  const response = await fetch('/api/v1/auth/register', {
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
  await readError(response)
  return loginAccount(input.account, input.password)
}

export async function forgotAccount(account: string) {
  const response = await fetch('/api/v1/auth/forgot-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(accountBody(account)),
  })
  return (await readError(response)) as { accepted: boolean; reset_token?: string; channel?: string; sms_sent_today?: number; sms_daily_cap?: number; sms_quota_warning?: boolean }
}

export async function resetWithSms(phone: string, code: string, password: string) {
  const response = await fetch('/api/v1/auth/reset-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, code, password }),
  })
  return (await readError(response)) as { reset: boolean }
}

export async function resetAccount(token: string, password: string) {
  const response = await fetch('/api/v1/auth/reset-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, password }),
  })
  return (await readError(response)) as { reset: boolean }
}

export async function sendLoginCode(account: string, purpose: 'login' | 'register' | 'reset_password' = 'login') {
  const response = await fetch('/api/v1/auth/code/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...accountBody(account), purpose }),
  })
  return (await readError(response)) as { sent: boolean; code?: string; channel?: string; purpose?: string; sms_sent_today?: number; sms_daily_cap?: number; sms_quota_warning?: boolean }
}

export async function wechatAuthorizeUrl() {
  const response = await fetch('/api/v1/auth/wechat/authorize')
  return (await readError(response)) as { url: string }
}

export async function completeWechatLogin(code: string, state: string) {
  const response = await fetch('/api/v1/auth/oauth/wechat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, state }),
  })
  const data = (await readError(response)) as SessionTokens
  writeSession(data)
  return data
}

export async function loginWithCode(account: string, code: string, recall?: string) {
  const response = await fetch('/api/v1/auth/code/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...accountBody(account), code, recall: recall || undefined }),
  })
  const data = (await readError(response)) as SessionTokens
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
