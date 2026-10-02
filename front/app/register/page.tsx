'use client'

import { FormEvent, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { AuthShell, authButton, authInput } from '@/components/auth-shell'
import { registerAccount } from '@/lib/session'

export default function RegisterPage() {
  const router = useRouter()
  const [displayName, setDisplayName] = useState('')
  const [account, setAccount] = useState('')
  const [password, setPassword] = useState('')
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
      await registerAccount({ account, password, displayName })
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
        {error && <p className="mt-4 rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        <button className={authButton} disabled={pending} type="submit">{pending ? '正在注册' : '注册并进入工作台'}</button>
      </form>
      <p className="mt-4 text-sm text-muted-foreground">已有账号？<Link href="/login" className="text-primary"> 登录</Link></p>
    </AuthShell>
  )
}
