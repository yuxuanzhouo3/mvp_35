'use client'

import { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams, useSearchParams } from 'next/navigation'
import { api, waitJob } from '@/lib/api'
import { channels, sameButton } from '../channels'

type Lead = {
  id: string
  company: string
  email: string | null
  market: string
  quality_score: number
  qualified: boolean
  source_channel: string
  platform: string
  status: string
  note: string
  exclude_from_ar: boolean
}

type Campaign = { id: string; name: string; status: string; draft: string | null; seed_analysis_id: string | null }
type LifeJob = { id: string; lead_id: string; status: string; reason: string; draft: string }
type Pop = { title: string; body: string; confirm: string; run: () => Promise<void> }

export default function ChannelPage() {
  return <Suspense fallback={<p className="text-sm text-muted-foreground">加载这一路…</p>}><ChannelDesk /></Suspense>
}

function ChannelDesk() {
  const params = useParams<{ channel: string }>()
  const search = useSearchParams()
  const channel = channels.find((item) => item.id === params.channel)
  const seed = search.get('seed_analysis_id') || ''
  const [platform, setPlatform] = useState(channel?.platforms[0] || '')
  const [leads, setLeads] = useState<Lead[]>([])
  const [picked, setPicked] = useState<string[]>([])
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [activation, setActivation] = useState<LifeJob[]>([])
  const [recall, setRecall] = useState<LifeJob[]>([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [pop, setPop] = useState<Pop | null>(null)
  const [view, setView] = useState<'discover' | 'leads' | 'outreach' | 'activation' | 'recall' | 'ledger'>('discover')

  async function reload() {
    const [leadData, campaignData, activationData, recallData] = await Promise.all([
      api<{ items: Lead[] }>(`/leads${seed ? `?seed_analysis_id=${encodeURIComponent(seed)}` : ''}`),
      api<{ items: Campaign[] }>('/campaigns'),
      api<{ items: LifeJob[] }>('/activation/jobs'),
      api<{ items: LifeJob[] }>('/recall/jobs'),
    ])
    setLeads(leadData.items)
    setCampaigns(campaignData.items)
    setActivation(activationData.items)
    setRecall(recallData.items)
  }

  useEffect(() => {
    if (!channel) return
    setPlatform(channel.platforms[0])
    reload().catch((reason: Error) => setError(reason.message))
  }, [channel?.id, seed])

  useEffect(() => {
    if (!pop) return
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setPop(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [pop])

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError('')
    try {
      await action()
      await reload()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '操作失败')
    } finally {
      setBusy(false)
    }
  }

  if (!channel) {
    return (
      <div className="flex max-w-xs flex-col gap-4">
        <p className="text-sm text-muted-foreground">没有这一路。</p>
        <Link href="/workspace/acquire" className={`${sameButton} border border-border bg-card`}>返回九路</Link>
      </div>
    )
  }

  const mine = leads.filter((lead) => lead.source_channel === channel.id)
  const views = [
    { id: 'discover', name: '发现线索' },
    { id: 'leads', name: '线索池' },
    { id: 'outreach', name: '触达' },
    { id: 'activation', name: '冷客启动' },
    { id: 'recall', name: '流失召回' },
    { id: 'ledger', name: '分成入账' },
  ] as const

  return (
    <div className="flex h-[calc(100dvh-13.5rem)] flex-col gap-3 overflow-hidden md:h-[calc(100dvh-11.5rem)]">
      <div className="flex shrink-0 flex-wrap items-end justify-between gap-2">
        <div>
          <Link href="/workspace/acquire" className="text-sm text-primary">返回九路</Link>
          <h1 className="text-2xl font-semibold tracking-tight">{channel.code} {channel.name}</h1>
        </div>
        <p className="max-w-xl text-xs leading-5 text-muted-foreground">{channel.copy}。六个功能在这一屏切换。{seed ? ` 种子报告 ${seed}。` : ''}</p>
      </div>
      {error && <p className="shrink-0 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
      {message && <p className="shrink-0 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{message}</p>}
      <div className="grid shrink-0 grid-cols-3 gap-2 lg:grid-cols-6">
        {views.map((item) => (
          <button key={item.id} type="button" className={`h-11 rounded-xl px-2 text-sm font-medium ${view === item.id ? 'bg-primary text-primary-foreground' : 'border border-border bg-card'}`} onClick={() => setView(item.id)}>
            {item.name}
          </button>
        ))}
      </div>
      <section className="min-h-0 flex-1 overflow-y-auto rounded-3xl border border-border bg-card p-4 md:p-5">
        {view === 'discover' && (
          <div>
            <h2 className="font-semibold">发现线索</h2>
            <p className="mt-1 text-sm text-muted-foreground">{channel.copy}</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,1fr)_10rem]">
              <select className="h-11 w-full rounded-xl border border-border bg-background px-3 text-sm" value={platform} aria-label="平台" onChange={(event) => setPlatform(event.target.value)}>
                {channel.platforms.map((item) => <option key={item}>{item}</option>)}
              </select>
              <button type="button" disabled={busy} className="h-11 rounded-xl bg-primary text-sm font-medium text-primary-foreground disabled:opacity-50" onClick={() => {
                void run(async () => {
                  const created = await api<{ job_id: string }>('/lead-searches', {
                    method: 'POST',
                    body: JSON.stringify({ channel: channel.id, platform, query: platform, seed_analysis_id: seed || null }),
                  })
                  const job = await waitJob(created.job_id)
                  if (job.status === 'failed') throw new Error(job.error?.message || '发现失败')
                  setMessage(channel.id === 'content_dh' ? '已发现线索。数智人仍是 DEMO 占位，不阻塞后续触达。' : '线索已写入统一线索池。')
                  setView('leads')
                })
              }}>开始发现</button>
            </div>
            {platform === 'digital_human_placeholder' && <p className="mt-2 text-xs text-muted-foreground">数智人 DEMO 为占位演示，不购买 10 小时包。</p>}
          </div>
        )}
        {view === 'leads' && (
          <div>
            <h2 className="font-semibold">线索池</h2>
            <p className="mt-1 text-sm text-muted-foreground">勾选后到「触达」创建活动。已选 {picked.length} 条。</p>
            <div className="mt-3 flex flex-col gap-2">
              {mine.map((lead) => (
                <article key={lead.id} className="grid items-center gap-2 rounded-xl border border-border p-3 sm:grid-cols-[auto_minmax(0,1fr)_auto]">
                  <input className="size-4" type="checkbox" checked={picked.includes(lead.id)} aria-label={`选择 ${lead.company}`} onChange={(event) => setPicked((currentIds) => event.target.checked ? [...currentIds, lead.id] : currentIds.filter((id) => id !== lead.id))} />
                  <span className="min-w-0 text-sm">
                    <span className="font-medium">{lead.company}</span>
                    <span className="mt-0.5 block truncate text-xs text-muted-foreground">{lead.email || '无邮箱'} · {lead.market} · {lead.platform} · {lead.quality_score}{lead.qualified ? '' : ' 未达标'} · {lead.status}</span>
                  </span>
                  <span className="grid grid-cols-2 gap-2">
                    <button type="button" className="h-9 rounded-lg border border-border px-3 text-sm" onClick={() => void run(() => api(`/leads/${lead.id}/signals`, { method: 'POST', body: JSON.stringify({ type: 'open' }) }).then(() => undefined))}>打开</button>
                    <button type="button" className="h-9 rounded-lg border border-border px-3 text-sm" onClick={() => setPop({
                      title: `赢单 · ${lead.company}`,
                      body: '标记赢单后，若发生在送达后 14 天内，计入获客率。',
                      confirm: '确认赢单',
                      run: async () => {
                        await api(`/leads/${lead.id}/signals`, { method: 'POST', body: JSON.stringify({ type: 'won' }) })
                        setMessage('已标记赢单。若发生在送达后 14 天内，计入获客率。')
                      },
                    })}>赢单</button>
                  </span>
                </article>
              ))}
              {mine.length === 0 && <p className="text-sm text-muted-foreground">这一路还没有线索。</p>}
            </div>
          </div>
        )}
        {view === 'outreach' && (
          <div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="font-semibold">触达</h2>
                <p className="mt-1 text-sm text-muted-foreground">生成草稿、批准，再发送。已选 {picked.length} 条。</p>
              </div>
              <button type="button" disabled={busy || picked.length === 0} className="h-11 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground disabled:opacity-50" onClick={() => {
                void run(async () => {
                  await api<Campaign>('/campaigns', {
                    method: 'POST',
                    body: JSON.stringify({ name: `${channel.code} ${new Date().toLocaleString('zh-CN')}`, lead_ids: picked, seed_analysis_id: seed || null, market_pack: 'cn_us' }),
                  })
                  setMessage('活动已创建。未批准不能发送。')
                })
              }}>用已选线索创建活动</button>
            </div>
            <div className="mt-3 flex flex-col gap-2">
              {campaigns.map((campaign) => (
                <article key={campaign.id} className="rounded-xl border border-border p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="truncate text-sm font-medium">{campaign.name}</h3>
                      <p className="text-xs text-muted-foreground">状态 {campaign.status}{campaign.draft ? ` · ${campaign.draft}` : ''}</p>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      <button type="button" className="h-9 rounded-lg border border-border px-3 text-sm" onClick={() => void run(() => api(`/campaigns/${campaign.id}/drafts`, { method: 'POST' }).then(() => setMessage('草稿已生成，等待批准。')))}>草稿</button>
                      <button type="button" className="h-9 rounded-lg border border-border px-3 text-sm" onClick={() => void run(() => api(`/campaigns/${campaign.id}/approve`, { method: 'POST' }).then(() => setMessage('已批准，并冻结受众快照。')))}>批准</button>
                      <button type="button" className="h-9 rounded-lg border border-border px-3 text-sm" onClick={() => setPop({
                        title: `发送 · ${campaign.name}`,
                        body: '确认后提交发送。演示环境使用 SES mock，不会真实发信。未批准时服务端会拒绝。',
                        confirm: '确认发送',
                        run: async () => {
                          const created = await api<{ job_id: string }>(`/campaigns/${campaign.id}/send`, { method: 'POST' })
                          const job = await waitJob(created.job_id)
                          if (job.status === 'failed') throw new Error(job.error?.message || '发送失败')
                          setMessage('发送任务完成。演示环境使用 SES mock，不会真实发信。')
                        },
                      })}>发送</button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </div>
        )}
        {view === 'activation' && (
          <LifePanel
            title="冷客启动"
            jobs={activation}
            busy={busy}
            empty="暂无冷启任务。"
            onScan={() => void run(async () => {
              const created = await api<{ job_id: string }>('/lifecycle/scan', { method: 'POST' })
              const job = await waitJob(created.job_id)
              if (job.status === 'failed') throw new Error(job.error?.message || '扫描失败')
              setMessage('规则扫描完成。合格且从未触达的线索进入冷启，打开后未回复的线索进入召回。')
            })}
            onApprove={(id) => void run(() => api(`/activation/jobs/${id}/approve`, { method: 'POST' }).then(() => undefined))}
            onSend={(job) => setPop({
              title: '发送冷启',
              body: job.draft || job.reason,
              confirm: '确认发送',
              run: async () => {
                const created = await api<{ job_id: string }>(`/activation/jobs/${job.id}/send`, { method: 'POST' })
                const finished = await waitJob(created.job_id)
                if (finished.status === 'failed') throw new Error(finished.error?.message || '发送失败')
              },
            })}
          />
        )}
        {view === 'recall' && (
          <LifePanel
            title="流失召回"
            jobs={recall}
            busy={busy}
            empty="暂无召回任务。"
            onApprove={(id) => void run(() => api(`/recall/jobs/${id}/approve`, { method: 'POST' }).then(() => undefined))}
            onSend={(job) => setPop({
              title: '发送召回',
              body: job.draft || job.reason,
              confirm: '确认发送',
              run: async () => {
                const created = await api<{ job_id: string }>(`/recall/jobs/${job.id}/send`, { method: 'POST' })
                const finished = await waitJob(created.job_id)
                if (finished.status === 'failed') throw new Error(finished.error?.message || '发送失败')
              },
            })}
          />
        )}
        {view === 'ledger' && (
          <div>
            <h2 className="font-semibold">分成入账</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">分成由服务端验签后入账。页面不请求签名，也不代发支付回调。RaaS 抽成不计入普通获客率。未开通的微信收款、自动成交和数智人购买不会出现在这里。</p>
          </div>
        )}
      </section>

      {pop && (
        <div className="fixed inset-0 z-[60] flex items-end justify-center bg-slate-950/40 p-4 sm:items-center" role="dialog" aria-modal="true" aria-label={pop.title}>
          <div className="w-full max-w-md rounded-2xl bg-card p-5 shadow-xl">
            <h2 className="text-lg font-semibold">{pop.title}</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{pop.body}</p>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <button type="button" className={`${sameButton} border border-border`} onClick={() => setPop(null)}>取消</button>
              <button type="button" disabled={busy} className={`${sameButton} bg-primary text-primary-foreground`} onClick={() => {
                const action = pop.run
                setPop(null)
                void run(action)
              }}>{pop.confirm}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function LifePanel({ title, jobs, busy, empty, onScan, onApprove, onSend }: { title: string; jobs: LifeJob[]; busy: boolean; empty: string; onScan?: () => void; onApprove: (id: string) => void; onSend: (job: LifeJob) => void }) {
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">{title}</h2>
        {onScan && <button type="button" disabled={busy} className="h-11 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground disabled:opacity-50" onClick={onScan}>规则扫描</button>}
      </div>
      <div className="mt-3 flex flex-col gap-2">
        {jobs.map((job) => (
          <article key={job.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border p-3 text-sm">
            <span className="min-w-0">
              <span>{job.reason} · {job.status}</span>
              <span className="mt-0.5 block truncate text-xs text-muted-foreground">{job.draft}</span>
            </span>
            <span className="grid grid-cols-2 gap-2">
              <button type="button" className="h-9 rounded-lg border border-border px-3 text-sm" onClick={() => onApprove(job.id)}>批准</button>
              <button type="button" className="h-9 rounded-lg border border-border px-3 text-sm" onClick={() => onSend(job)}>发送</button>
            </span>
          </article>
        ))}
        {jobs.length === 0 && <p className="text-sm text-muted-foreground">{empty}</p>}
      </div>
    </div>
  )
}
