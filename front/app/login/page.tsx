'use client'

import { FormEvent, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense } from 'react'
import { AuthShell, authButton, authInput } from '@/components/auth-shell'
import { loginAccount, loginWithCode, safeNext, sendLoginCode } from '@/lib/session'

export default function LoginPage() {
  return <Suspense fallback={<p className="p-8 text-sm text-muted-foreground">加载登录…</p>}><LoginForm /></Suspense>
}

function LoginForm() {
  const router = useRouter()
  const next = safeNext(useSearchParams().get('next'))
  const [account, setAccount] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [sentCode, setSentCode] = useState('')
  const [mode, setMode] = useState<'password' | 'code'>('password')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setError('')
    try {
      if (mode === 'code') await loginWithCode(account, code)
      else await loginAccount(account, password)
      router.replace(next)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '登录失败')
    } finally {
      setPending(false)
    }
  }

  return (
    <AuthShell title="登录工作台" copy="使用注册时的邮箱、手机号或用户名。微信、SSO 和多因素验证未开通，这里不提供入口。">
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
            <button type="button" className="text-sm text-primary" onClick={() => {
              void sendLoginCode(account).then((result) => setSentCode(result.code || '')).catch((reason: Error) => setError(reason.message))
            }}>发送验证码</button>
            {sentCode && <p className="mt-2 text-xs text-muted-foreground">演示环境验证码：{sentCode}</p>}
            <label className="mt-3 block text-sm font-medium">
              验证码
              <input value={code} onChange={(event) => setCode(event.target.value)} inputMode="numeric" autoComplete="one-time-code" required className={authInput} />
            </label>
          </div>
        )}
        {error && <p className="mt-4 rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        <button className={authButton} disabled={pending} type="submit">{pending ? '正在登录' : '登录'}</button>
      </form>
      <div className="mt-4 flex justify-between text-sm text-muted-foreground">
        <Link href="/forgot" className="hover:text-foreground">忘记密码</Link>
        <Link href="/register" className="hover:text-foreground">注册账号</Link>
      </div>
    </AuthShell>
  )
}
