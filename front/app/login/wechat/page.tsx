'use client'

import { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { AuthShell } from '@/components/auth-shell'
import { completeWechatLogin } from '@/lib/session'

export default function WechatCallbackPage() {
  return (
    <Suspense fallback={<p className="p-8 text-sm text-muted-foreground">正在完成微信登录…</p>}>
      <WechatCallback />
    </Suspense>
  )
}

function WechatCallback() {
  const router = useRouter()
  const params = useSearchParams()
  const [error, setError] = useState('')

  useEffect(() => {
    const code = params.get('code') || ''
    const state = params.get('state') || ''
    if (!code || !state) {
      setError('微信没有返回登录凭证')
      return
    }
    void completeWechatLogin(code, state)
      .then(() => router.replace('/workspace'))
      .catch((reason: Error) => setError(reason.message))
  }, [params, router])

  return (
    <AuthShell title="微信登录" copy="正在用微信返回的授权码换取会话。">
      {error ? <p className="rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : <p className="text-sm text-muted-foreground">请稍候…</p>}
    </AuthShell>
  )
}
