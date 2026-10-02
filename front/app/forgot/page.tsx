'use client'

import { FormEvent, useState } from 'react'
import Link from 'next/link'
import { AuthShell, authButton, authInput } from '@/components/auth-shell'
import { forgotAccount } from '@/lib/session'

export default function ForgotPage() {
  const [account, setAccount] = useState('')
  const [token, setToken] = useState('')
  const [accepted, setAccepted] = useState(false)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!account.includes('@') && !/^\+?\d{6,}$/.test(account.trim())) {
      setError('请填写邮箱或手机号')
      return
    }
    setPending(true)
    setError('')
    try {
      const result = await forgotAccount(account)
      setAccepted(true)
      setToken(result.reset_token || '')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '发送失败')
    } finally {
      setPending(false)
    }
  }

  return (
    <AuthShell title="找回密码" copy="演示环境会直接给出重置凭证。正式环境只发送邮件或短信，不在页面返回凭证。">
      <form onSubmit={onSubmit}>
        <label className="block text-sm font-medium">
          邮箱或手机号
          <input value={account} onChange={(event) => setAccount(event.target.value)} required className={authInput} />
        </label>
        {error && <p className="mt-4 rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        <button className={authButton} disabled={pending} type="submit">{pending ? '正在提交' : '获取重置凭证'}</button>
      </form>
      {token && (
        <p className="mt-4 text-sm leading-6">
          重置凭证已生成。<Link className="text-primary" href={`/reset?token=${encodeURIComponent(token)}`}>去设置新密码</Link>
        </p>
      )}
      {accepted && !token && <p className="mt-4 text-sm text-muted-foreground">若账号存在，重置请求已受理。</p>}
      <p className="mt-4 text-sm"><Link href="/login" className="text-primary">返回登录</Link></p>
    </AuthShell>
  )
}
