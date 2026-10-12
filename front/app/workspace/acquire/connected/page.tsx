'use client'

import { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { api } from '@/lib/api'

type Saved = { channel: string; platform: string; mode_label: string; status: string }

export default function ConnectedPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">正在确认平台登录…</p>}>
      <Connected />
    </Suspense>
  )
}

function Connected() {
  const search = useSearchParams()
  const [saved, setSaved] = useState<Saved | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const code = search.get('code') || search.get('auth_code') || ''
    const state = search.get('state') || search.get('nonce') || ''
    if (!code || !state) {
      setError('平台没有把授权码带回。请从获客页重新登录。')
      return
    }
    api<Saved>('/channel-accounts/callback', { method: 'POST', body: JSON.stringify({ state, code }) })
      .then(setSaved)
      .catch((reason: Error) => setError(reason.message))
  }, [search])

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-4 py-10">
      <h1 className="text-2xl font-semibold">平台账号</h1>
      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
      {saved && <p className="text-sm">{saved.platform} 已登录{saved.mode_label ? `。${saved.mode_label}` : ''}。获客动作下一步再接。</p>}
      <Link href={saved ? `/workspace/acquire/${saved.channel}` : '/workspace/acquire'} className="text-sm text-primary">返回这一路</Link>
    </div>
  )
}
