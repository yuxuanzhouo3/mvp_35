'use client'

import { FormEvent, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { AuthShell, authButton, authInput } from '@/components/auth-shell'
import { SmsQuotaDialog } from '@/components/sms-quota-dialog'
import { registerAccount, sendLoginCode } from '@/lib/session'

export default function RegisterPage() {
  const router = useRouter()
  const [displayName, setDisplayName] = useState('')
  const [account, setAccount] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [sentCode, setSentCode] = useState('')
  const [sentNote, setSentNote] = useState('')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const [quota, setQuota] = useState<{ count: number; cap: number } | null>(null)
  const [inviteCode, setInviteCode] = useState('')

  useEffect(() => {
    setInviteCode(new URLSearchParams(window.location.search).get('invite') || '')
  }, [])

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
      await registerAccount({ account, password, displayName, code, inviteCode })
      router.replace('/workspace')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '注册失败')
    } finally {
      setPending(false)
    }
  }

  return (
    <AuthShell title="注册卖家账号" copy="注册后进入你自己的工作台。套餐默认免费，付费在账单页下单，支付结果以后台回调为准。">
      <form onSubmit={onSubmit}>
        <label className="block text-sm font-medium">
          显示名
          <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} className={authInput} />
        </label>
        <label className="mt-4 block text-sm font-medium">
          邮箱或手机号
          <input value={account} onChange={(event) => setAccount(event.target.value)} autoComplete="username" required className={authInput} />
        </label>
        <label className="mt-4 block text-sm font-medium">
          密码
          <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="new-password" required minLength={6} className={authInput} />
        </label>
        <div className="mt-4">
          <button
            type="button"
            className="text-sm text-primary"
            onClick={() => {
              setError('')
              void sendLoginCode(account, 'register')
                .then((result) => {
                  setSentCode(result.code || '')
                  if (result.sms_quota_warning) setQuota({ count: result.sms_sent_today || 0, cap: result.sms_daily_cap || 10 })
                  setSentNote(result.channel === 'sms' ? '验证码已发到手机，5 分钟内有效。' : result.channel ? '验证码已发送，请查收后填写。' : '')
                })
                .catch((reason: Error) => setError(reason.message))
            }}
          >
            发送邮箱或短信验证码
          </button>
          {sentNote && <p className="mt-2 text-xs text-muted-foreground">{sentNote}</p>}
          {sentCode && <p className="mt-2 text-xs text-muted-foreground">演示环境验证码：{sentCode}</p>}
          <label className="mt-3 block text-sm font-medium">
            验证码
            <input value={code} onChange={(event) => setCode(event.target.value)} inputMode="numeric" autoComplete="one-time-code" className={authInput} />
          </label>
          <p className="mt-2 text-xs text-muted-foreground">邮箱验证码 10 分钟内有效，短信验证码 5 分钟内有效。填写后再提交。</p>
        </div>
        {inviteCode && <p className="mt-4 text-sm text-muted-foreground">邀请码 {inviteCode}</p>}
        {error && <p className="mt-4 rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        <button className={authButton} disabled={pending} type="submit">{pending ? '正在注册' : '注册并进入工作台'}</button>
      </form>
      {quota && <SmsQuotaDialog count={quota.count} cap={quota.cap} onClose={() => setQuota(null)} />}
      <p className="mt-4 text-sm text-muted-foreground">已有账号？<Link href="/login" className="text-primary"> 登录</Link></p>
    </AuthShell>
  )
}
