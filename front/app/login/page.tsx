'use client'

import { FormEvent, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense } from 'react'
import { AuthShell, authButton, authInput } from '@/components/auth-shell'
import { LegalConsent, rememberLegalAcceptance } from '@/components/legal-consent'
import { SmsQuotaDialog } from '@/components/sms-quota-dialog'
import { readClient } from '@/lib/client-adapter'
import { loginAccount, loginWithCode, safeNext, sendLoginCode, wechatAuthorizeUrl } from '@/lib/session'

export default function LoginPage() {
  return <Suspense fallback={<p className="p-8 text-sm text-muted-foreground">加载登录…</p>}><LoginForm /></Suspense>
}

function LoginForm() {
  const router = useRouter()
  const params = useSearchParams()
  const next = safeNext(params.get('next'))
  const recall = params.get('recall') || ''
  const [account, setAccount] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [sentCode, setSentCode] = useState('')
  const [sentNote, setSentNote] = useState('')
  const [mode, setMode] = useState<'password' | 'code'>('password')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const [sending, setSending] = useState(false)
  const [miniprogram, setMiniprogram] = useState(false)
  const [quota, setQuota] = useState<{ count: number; cap: number } | null>(null)
  const [accepted, setAccepted] = useState(false)

  useEffect(() => {
    setMiniprogram(readClient()?.shell === 'miniprogram')
  }, [])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!accepted) {
      setError('请先勾选《隐私政策》《CIO 合规》和《用户协议》。')
      return
    }
    setPending(true)
    setError('')
    try {
      if (mode === 'code') await loginWithCode(account, code, recall)
      else await loginAccount(account, password, recall)
      rememberLegalAcceptance()
      router.replace(next)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '登录失败')
    } finally {
      setPending(false)
    }
  }

  return (
    <AuthShell title="登录工作台" copy="使用邮箱、手机号或用户名。验证码发到邮箱后 10 分钟内有效，短信 5 分钟内有效。">
      <div className="mb-4 flex gap-2 text-sm">
        <button type="button" className={`rounded-lg px-3 py-1.5 ${mode === 'password' ? 'bg-primary text-primary-foreground' : 'border border-border'}`} onClick={() => setMode('password')}>密码</button>
        <button type="button" className={`rounded-lg px-3 py-1.5 ${mode === 'code' ? 'bg-primary text-primary-foreground' : 'border border-border'}`} onClick={() => setMode('code')}>验证码</button>
      </div>
      <form onSubmit={onSubmit}>
        <label className="block text-sm font-medium">
          邮箱、手机或用户名
          <input value={account} onChange={(event) => setAccount(event.target.value)} autoComplete="username" required className={authInput} />
        </label>
        {mode === 'password' ? (
          <label className="mt-4 block text-sm font-medium">
            密码
            <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" required className={authInput} />
          </label>
        ) : (
          <div className="mt-4">
            <button type="button" className="text-sm text-primary disabled:opacity-50" disabled={sending} onClick={() => {
              setError('')
              setSending(true)
              void sendLoginCode(account).then((result) => {
                setSentCode(result.code || '')
                if (result.sms_quota_warning) setQuota({ count: result.sms_sent_today || 0, cap: result.sms_daily_cap || 10 })
                setSentNote(
                  result.channel === 'sms'
                    ? '验证码已发到手机，5 分钟内有效。'
                    : result.channel === 'email'
                      ? '验证码已发到邮箱，10 分钟内有效。'
                      : result.code
                        ? ''
                        : '若账号存在，验证码已发送。',
                )
              }).catch((reason: Error) => setError(reason.message)).finally(() => setSending(false))
            }}>{sending ? '正在发送' : '发送验证码'}</button>
            {sentNote && <p className="mt-2 text-xs text-muted-foreground">{sentNote}</p>}
            {sentCode && <p className="mt-2 text-xs text-muted-foreground">演示环境验证码：{sentCode}</p>}
            <label className="mt-3 block text-sm font-medium">
              验证码
              <input value={code} onChange={(event) => setCode(event.target.value)} inputMode="numeric" autoComplete="one-time-code" required className={authInput} />
            </label>
          </div>
        )}
        <LegalConsent checked={accepted} onChange={setAccepted} />
        {error && <p className="mt-4 rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        <button className={authButton} disabled={pending || !accepted} type="submit">{pending ? '正在登录' : '登录'}</button>
      </form>
      {miniprogram && (
        <button
          type="button"
          className="mt-4 w-full rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-50"
          disabled={!accepted}
          onClick={() => {
            if (!accepted) {
              setError('请先勾选《隐私政策》《CIO 合规》和《用户协议》。')
              return
            }
            setError('')
            void wechatAuthorizeUrl()
              .then((result) => window.location.assign(result.url))
              .catch((reason: Error) => setError(reason.message))
          }}
        >
          微信登录
        </button>
      )}
      {quota && <SmsQuotaDialog count={quota.count} cap={quota.cap} onClose={() => setQuota(null)} />}
      <div className="mt-4 flex justify-between text-sm text-muted-foreground">
        <Link href="/forgot" className="hover:text-foreground">忘记密码</Link>
        <Link href="/register" className="hover:text-foreground">注册账号</Link>
      </div>
    </AuthShell>
  )
}
