'use client'

import { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams, useSearchParams } from 'next/navigation'
import { api, waitJob } from '@/lib/api'
import { channels, parts, sameButton, type PartId } from '../channels'

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

export default function ChannelPage() {
  return <Suspense fallback={<p className="text-sm text-muted-foreground">加载这一路…</p>}><ChannelDesk /></Suspense>
}

function ChannelDesk() {
  const params = useParams<{ channel: string }>()
  const search = useSearchParams()
  const channel = channels.find((item) => item.id === params.channel)
  const seed = search.get('seed_analysis_id') || ''
  const [part, setPart] = useState<PartId | null>(null)
  const [platform, setPlatform] = useState(channel?.platforms[0] || '')
  const [leads, setLeads] = useState<Lead[]>([])
  const [picked, setPicked] = useState<string[]>([])
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [activation, setActivation] = useState<LifeJob[]>([])
  const [recall, setRecall] = useState<LifeJob[]>([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

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
    if (!part) return
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setPart(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [part])

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
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">没有这一路。</p>
        <Link href="/workspace/acquire" className={`${sameButton} border border-border bg-card`}>返回九路</Link>
      </div>
    )
  }

  const mine = leads.filter((lead) => lead.source_channel === channel.id)
  const current = parts.find((item) => item.id === part)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/workspace/acquire" className="text-sm text-primary">返回九路</Link>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">{channel.code} {channel.name}</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
          {channel.copy}。每个功能单独打开，方便在手机上操作。
          {seed ? ` 当前种子报告 ${seed}。` : ''}
        </p>
      </div>
      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
      {message && <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{message}</p>}
      <div className="grid grid-cols-2 gap-3">
        {parts.map((item) => (
          <button key={item.id} type="button" className={`${sameButton} border border-border bg-card`} onClick={() => setPart(item.id)}>
            {item.name}
          </button>
        ))}
      </div>

      {current && (
        <div className="fixed inset-0 z-[60] flex flex-col bg-background" role="dialog" aria-modal="true" aria-label={current.name}>
          <div className="container flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto py-4 pb-[max(2rem,env(safe-area-inset-bottom))]">
            <button type="button" className={`${sameButton} shrink-0 border border-border bg-card`} onClick={() => setPart(null)}>返回 {channel.code}</button>
            <div>
              <p className="text-xs font-medium text-primary">{channel.code} {channel.name}</p>
              <h2 className="mt-1 text-2xl font-semibold">{current.name}</h2>
            </div>
            {part === 'discover' && (
              <div className="flex flex-col gap-3">
                <p className="text-sm leading-6 text-muted-foreground">{channel.copy}</p>
                <label className="text-sm">
                  平台
                  <select className="mt-2 h-12 w-full rounded-xl border border-border bg-background px-3 text-sm" value={platform} onChange={(event) => setPlatform(event.target.value)}>
                    {channel.platforms.map((item) => <option key={item}>{item}</option>)}
                  </select>
                </label>
                <button type="button" disabled={busy} className={`${sameButton} bg-primary text-primary-foreground`} onClick={() => {
                  void run(async () => {
                    const created = await api<{ job_id: string }>('/lead-searches', {
                      method: 'POST',
                      body: JSON.stringify({ channel: channel.id, platform, query: platform, seed_analysis_id: seed || null }),
                    })
                    const job = await waitJob(created.job_id)
                    if (job.status === 'failed') throw new Error(job.error?.message || '发现失败')
                    setMessage(channel.id === 'content_dh' ? '已发现线索。数智人仍是 DEMO 占位，不阻塞后续触达。' : '线索已写入统一线索池。')
                  })
                }}>开始发现</button>
                {platform === 'digital_human_placeholder' && <p className="text-xs text-muted-foreground">数智人 DEMO 为占位演示，不购买 10 小时包。</p>}
              </div>
            )}
            {part === 'leads' && (
              <div className="flex flex-col gap-3">
                {mine.map((lead) => (
                  <article key={lead.id} className="rounded-2xl border border-border p-4">
                    <label className="flex items-start gap-3 text-sm">
                      <input className="mt-1 size-4" type="checkbox" checked={picked.includes(lead.id)} aria-label={`选择 ${lead.company}`} onChange={(event) => setPicked((currentIds) => event.target.checked ? [...currentIds, lead.id] : currentIds.filter((id) => id !== lead.id))} />
                      <span>
                        <span className="font-medium">{lead.company}</span>
                        <span className="mt-1 block text-xs leading-5 text-muted-foreground">{lead.email || '无邮箱'} · {lead.market} · {lead.platform} · {lead.quality_score}{lead.qualified ? '' : ' 未达标'} · {lead.status}{lead.exclude_from_ar ? ' · 不计入 AR' : ''}{lead.note ? ` · ${lead.note}` : ''}</span>
                      </span>
                    </label>
                    <div className="mt-3 grid grid-cols-2 gap-3">
                      <button type="button" className={`${sameButton} border border-border`} onClick={() => void run(() => api(`/leads/${lead.id}/signals`, { method: 'POST', body: JSON.stringify({ type: 'open' }) }).then(() => undefined))}>打开</button>
                      <button type="button" className={`${sameButton} border border-border`} onClick={() => void run(() => api(`/leads/${lead.id}/signals`, { method: 'POST', body: JSON.stringify({ type: 'won' }) }).then(() => setMessage('已标记赢单。若发生在送达后 14 天内，计入获客率。')))}>赢单</button>
                    </div>
                  </article>
                ))}
                {mine.length === 0 && <p className="text-sm text-muted-foreground">这一路还没有线索。</p>}
              </div>
            )}
            {part === 'outreach' && (
              <div className="flex flex-col gap-3">
                <p className="text-sm leading-6 text-muted-foreground">顺序是生成草稿、人工批准、再发送。已选 {picked.length} 条这一路的线索。</p>
                <button type="button" disabled={busy || picked.length === 0} className={`${sameButton} bg-primary text-primary-foreground`} onClick={() => {
                  void run(async () => {
                    await api<Campaign>('/campaigns', {
                      method: 'POST',
                      body: JSON.stringify({ name: `${channel.code} ${new Date().toLocaleString('zh-CN')}`, lead_ids: picked, seed_analysis_id: seed || null, market_pack: 'cn_us' }),
                    })
                    setMessage('活动已创建。未批准不能发送。')
                  })
                }}>用已选线索创建活动</button>
                {campaigns.map((campaign) => (
                  <article key={campaign.id} className="rounded-2xl border border-border p-4">
                    <h3 className="font-medium">{campaign.name}</h3>
                    <p className="mt-1 text-xs text-muted-foreground">状态 {campaign.status}{campaign.seed_analysis_id ? ` · 种子 ${campaign.seed_analysis_id}` : ''}</p>
                    {campaign.draft && <p className="mt-2 text-sm leading-6 text-muted-foreground">{campaign.draft}</p>}
                    <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
                      <button type="button" className={`${sameButton} border border-border`} onClick={() => void run(() => api(`/campaigns/${campaign.id}/drafts`, { method: 'POST' }).then(() => setMessage('草稿已生成，等待批准。')))}>生成草稿</button>
                      <button type="button" className={`${sameButton} border border-border`} onClick={() => void run(() => api(`/campaigns/${campaign.id}/approve`, { method: 'POST' }).then(() => setMessage('已批准，并冻结受众快照。')))}>批准</button>
                      <button type="button" className={`${sameButton} border border-border`} onClick={() => void run(async () => {
                        const created = await api<{ job_id: string }>(`/campaigns/${campaign.id}/send`, { method: 'POST' })
                        const job = await waitJob(created.job_id)
                        if (job.status === 'failed') throw new Error(job.error?.message || '发送失败')
                        setMessage('发送任务完成。演示环境使用 SES mock，不会真实发信。')
                      })}>发送</button>
                    </div>
                  </article>
                ))}
              </div>
            )}
            {part === 'activation' && (
              <LifePanel
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
                onSend={(id) => void run(async () => {
                  const created = await api<{ job_id: string }>(`/activation/jobs/${id}/send`, { method: 'POST' })
                  const job = await waitJob(created.job_id)
                  if (job.status === 'failed') throw new Error(job.error?.message || '发送失败')
                })}
              />
            )}
            {part === 'recall' && (
              <LifePanel
                jobs={recall}
                busy={busy}
                empty="暂无召回任务。"
                onApprove={(id) => void run(() => api(`/recall/jobs/${id}/approve`, { method: 'POST' }).then(() => undefined))}
                onSend={(id) => void run(async () => {
                  const created = await api<{ job_id: string }>(`/recall/jobs/${id}/send`, { method: 'POST' })
                  const job = await waitJob(created.job_id)
                  if (job.status === 'failed') throw new Error(job.error?.message || '发送失败')
                })}
              />
            )}
            {part === 'ledger' && (
              <p className="text-sm leading-6 text-muted-foreground">分成由服务端验签后入账。页面不请求签名，也不代发支付回调。RaaS 抽成不计入普通获客率。未开通的微信收款、自动成交和数智人购买不会出现在这里。</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function LifePanel({ jobs, busy, empty, onScan, onApprove, onSend }: { jobs: LifeJob[]; busy: boolean; empty: string; onScan?: () => void; onApprove: (id: string) => void; onSend: (id: string) => void }) {
  return (
    <div className="flex flex-col gap-3">
      {onScan && <button type="button" disabled={busy} className={`${sameButton} bg-primary text-primary-foreground`} onClick={onScan}>规则扫描</button>}
      {jobs.map((job) => (
        <article key={job.id} className="rounded-2xl border border-border p-4 text-sm">
          <p>{job.reason} · {job.status}</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{job.draft}</p>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <button type="button" className={`${sameButton} border border-border`} onClick={() => onApprove(job.id)}>批准</button>
            <button type="button" className={`${sameButton} border border-border`} onClick={() => onSend(job.id)}>发送</button>
          </div>
        </article>
      ))}
      {jobs.length === 0 && <p className="text-sm text-muted-foreground">{empty}</p>}
    </div>
  )
}
