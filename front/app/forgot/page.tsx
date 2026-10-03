'use client'

import { FormEvent, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { AuthShell, authButton, authInput } from '@/components/auth-shell'
import { forgotAccount, resetWithSms } from '@/lib/session'

export default function ForgotPage() {
  const router = useRouter()
  const [account, setAccount] = useState('')
  const [token, setToken] = useState('')
  const [emailed, setEmailed] = useState(false)
  const [smsSent, setSmsSent] = useState(false)
  const [smsCode, setSmsCode] = useState('')
  const [password, setPassword] = useState('')
  const [accepted, setAccepted] = useState(false)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const compact = account.trim().replace(/[\s-]/g, '')
    if (!compact.includes('@') && !/^\+?\d{6,}$/.test(compact)) {
      setError('请填写邮箱或手机号')
      return
    }
    setPending(true)
    setError('')
    try {
      const result = await forgotAccount(account)
      setAccepted(true)
      setEmailed(result.channel === 'email')
      setSmsSent(result.channel === 'sms')
      setToken(result.reset_token || '')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '发送失败')
    } finally {
      setPending(false)
    }
  }

  return (
    <AuthShell title="找回密码" copy="邮箱收到重置链接。手机收到 5 分钟内有效的验证码，填在本页即可设置新密码。">
      <form onSubmit={onSubmit}>
        <label className="block text-sm font-medium">
          邮箱或手机号
          <input value={account} onChange={(event) => setAccount(event.target.value)} required className={authInput} />
        </label>
        {error && <p className="mt-4 rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        <button className={authButton} disabled={pending} type="submit">{pending ? '正在发送' : '发送重置验证'}</button>
      </form>
      {token && (
        <p className="mt-4 text-sm leading-6">
          重置凭证已生成。<Link className="text-primary" href={`/reset?token=${encodeURIComponent(token)}`}>去设置新密码</Link>
        </p>
      )}
      {emailed && <p className="mt-4 text-sm text-muted-foreground">若账号存在，重置链接已发到邮箱，1 小时内有效。</p>}
      {smsSent && (
        <form
          className="mt-4"
          onSubmit={(event) => {
            event.preventDefault()
            setPending(true)
            setError('')
            void resetWithSms(account, smsCode, password)
              .then(() => router.replace('/login'))
              .catch((reason: Error) => setError(reason.message))
              .finally(() => setPending(false))
          }}
        >
          <p className="text-sm text-muted-foreground">若账号存在，验证码已发到手机，5 分钟内有效。</p>
          <label className="mt-3 block text-sm font-medium">
            短信验证码
            <input value={smsCode} onChange={(event) => setSmsCode(event.target.value)} inputMode="numeric" autoComplete="one-time-code" required className={authInput} />
          </label>
          <label className="mt-4 block text-sm font-medium">
            新密码
            <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="new-password" required minLength={6} className={authInput} />
          </label>
          <button className={authButton} disabled={pending} type="submit">{pending ? '正在保存' : '保存并返回登录'}</button>
        </form>
      )}
      {accepted && !token && !emailed && !smsSent && <p className="mt-4 text-sm text-muted-foreground">若账号存在，重置请求已受理。</p>}
      <p className="mt-4 text-sm"><Link href="/login" className="text-primary">返回登录</Link></p>
    </AuthShell>
  )
}
