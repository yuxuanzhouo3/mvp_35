'use client'

import { FormEvent, Suspense, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { AuthShell, authButton, authInput } from '@/components/auth-shell'
import { resetAccount } from '@/lib/session'

export default function ResetPage() {
  return <Suspense fallback={<p className="p-8 text-sm text-muted-foreground">加载重置页…</p>}><ResetForm /></Suspense>
}

function ResetForm() {
  const router = useRouter()
  const token = useSearchParams().get('token') || ''
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setError('')
    try {
      await resetAccount(token, password)
      router.replace('/login')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '重置失败')
    } finally {
      setPending(false)
    }
  }

  return (
    <AuthShell title="设置新密码" copy="重置后旧会话会失效，需要重新登录。">
      <form onSubmit={onSubmit}>
        <label className="block text-sm font-medium">
          重置凭证
          <input value={token} readOnly className={authInput} />
        </label>
        <label className="mt-4 block text-sm font-medium">
          新密码
          <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="new-password" required minLength={6} className={authInput} />
        </label>
        {error && <p className="mt-4 rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        <button className={authButton} disabled={pending || !token} type="submit">{pending ? '正在保存' : '保存并返回登录'}</button>
      </form>
      <p className="mt-4 text-sm"><Link href="/forgot" className="text-primary">重新获取凭证</Link></p>
    </AuthShell>
  )
}
