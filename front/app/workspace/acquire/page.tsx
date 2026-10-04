'use client'

import { Suspense, useEffect } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { channels } from './channels'

export default function AcquirePage() {
  return <Suspense fallback={<p className="text-sm text-muted-foreground">加载获客工作台…</p>}><AcquireHome /></Suspense>
}

function AcquireHome() {
  const params = useSearchParams()
  const router = useRouter()
  const channel = params.get('channel')
  const seed = params.get('seed_analysis_id')

  useEffect(() => {
    if (!channel || !channels.some((item) => item.id === channel)) return
    const query = seed ? `?seed_analysis_id=${encodeURIComponent(seed)}` : ''
    router.replace(`/workspace/acquire/${channel}${query}`)
  }, [channel, seed, router])

  return (
    <div className="flex flex-col gap-4 md:h-[calc(100dvh-11.5rem)]">
      <div className="shrink-0">
        <span className="eyebrow">路径 B · 九路获客</span>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">线索、触达、成交与召回</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">点开一路，在下一页完成发现、线索、触达、冷启、召回和分成。九路写入同一线索池。</p>
      </div>
      <div className="grid flex-1 grid-cols-2 gap-3 max-md:auto-rows-[9.5rem] sm:gap-4 md:grid-rows-3 lg:grid-cols-3">
        {channels.map((item) => (
          <Link key={item.id} href={`/workspace/acquire/${item.id}`} className="flex h-full min-h-36 flex-col items-center justify-center rounded-3xl border border-border bg-card px-4 py-5 text-center">
            <span className="text-sm font-semibold text-primary">{item.code}</span>
            <span className="mt-2 text-lg font-semibold sm:text-xl">{item.name}</span>
            <span className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground sm:text-sm">{item.copy}</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
