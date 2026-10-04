'use client'

import { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams, useSearchParams } from 'next/navigation'
import { api, waitJob } from '@/lib/api'
import { ResultDesk } from '@/components/result-desk'
import { RouteBar } from '@/components/route-bar'
import { DEFAULT_ROUTE, readTradeRoute, TRADE_ROUTES, type RouteId } from '@/lib/trade-route'
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
  created_at?: string
}

type Campaign = { id: string; name: string; status: string; draft: string | null; seed_analysis_id: string | null; created_at?: string }
type LifeJob = { id: string; lead_id: string; status: string; reason: string; draft: string; created_at?: string; delivered_at?: string | null }
type Pop = { title: string; body: string; confirm: string; run: () => Promise<void> }
type ReachId = 'email' | 'sms' | 'wechat' | 'phone'

const reachForms: { id: ReachId; name: string }[] = [
  { id: 'email', name: '邮箱' },
  { id: 'sms', name: '短信' },
  { id: 'wechat', name: '微信' },
  { id: 'phone', name: '电话' },
]

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
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [pop, setPop] = useState<Pop | null>(null)
  const [view, setView] = useState<'discover' | 'leads' | 'outreach' | 'activation' | 'recall' | 'ledger'>(params.channel === 'raas' ? 'ledger' : 'discover')
  const [reach, setReach] = useState<ReachId>('email')
  const [route, setRoute] = useState<RouteId>(DEFAULT_ROUTE)

  useEffect(() => {
    function sync() {
      setRoute(readTradeRoute())
    }
    sync()
    window.addEventListener('pickglobal-route', sync)
    return () => window.removeEventListener('pickglobal-route', sync)
  }, [])

  async function reload() {
    const [leadData, campaignData, activationData] = await Promise.all([
      api<{ items: Lead[] }>(`/leads${seed ? `?seed_analysis_id=${encodeURIComponent(seed)}` : ''}`),
      api<{ items: Campaign[] }>('/campaigns'),
      api<{ items: LifeJob[] }>('/activation/jobs'),
    ])
    setLeads(leadData.items)
    setCampaigns(campaignData.items)
    setActivation(activationData.items)
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

  const mine = leads.filter((lead) => lead.source_channel === channel.id && lead.market === TRADE_ROUTES[route].target_market)
  const baseViews = [
    { id: 'discover', name: '发现线索' },
    { id: 'leads', name: '线索池' },
    { id: 'outreach', name: '触达' },
    { id: 'activation', name: '冷客启动' },
    { id: 'recall', name: '流失召回' },
    { id: 'ledger', name: channel.id === 'raas' ? '结果分佣' : '分成入账' },
  ] as const
  const views = channel.id === 'raas' ? [baseViews[5], ...baseViews.slice(0, 5)] : baseViews

  return (
    <div className="work-desk flex flex-col gap-2 overflow-hidden">
      <RouteBar />
      <div className="flex shrink-0 flex-wrap items-end justify-between gap-2">
        <div>
          <Link href="/workspace/acquire" className="text-sm text-primary">返回九路</Link>
          <h1 className="text-2xl font-semibold tracking-tight">{channel.code} {channel.name}</h1>
        </div>
        <p className="max-w-xl text-xs leading-5 text-muted-foreground">{channel.copy}{seed ? ` · 种子报告 ${seed}` : ''}</p>
      </div>
      {error && <p className="shrink-0 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
      {message && <p className="shrink-0 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{message}</p>}
      <div className="grid shrink-0 grid-cols-3 gap-2 lg:grid-cols-6">
        {views.map((item) => (
          <button key={item.id} type="button" className={`h-11 rounded-xl px-2 text-sm font-medium ${view === item.id ? 'bg-blue-600 text-white' : 'border border-border bg-white text-slate-700 dark:bg-card dark:text-foreground'}`} onClick={() => setView(item.id)}>
            {item.name}
          </button>
        ))}
      </div>
      <section className="panel-frame min-h-0 flex-1 overflow-y-auto rounded-3xl bg-card p-4 md:p-5">
        {view === 'discover' && (
          <div>
            <h2 className="font-semibold">发现线索</h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,1fr)_10rem]">
              <select className="h-11 w-full rounded-xl border-0 bg-muted px-3 text-sm outline-none" value={platform} aria-label="平台" onChange={(event) => setPlatform(event.target.value)}>
                {channel.platforms.map((item) => <option key={item}>{item}</option>)}
              </select>
              <button type="button" disabled={busy} className="h-11 rounded-xl bg-primary text-sm font-medium text-primary-foreground disabled:opacity-50" onClick={() => {
                void run(async () => {
                  const created = await api<{ job_id: string }>('/lead-searches', {
                    method: 'POST',
                    body: JSON.stringify({ channel: channel.id, platform, query: platform, seed_analysis_id: seed || null, route }),
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
            <div className="mt-3">
              <ResultDesk
                items={mine}
                placeholder="搜索公司、邮箱、平台"
                keywords={(lead) => `${lead.company} ${lead.email || ''} ${lead.platform} ${lead.market} ${lead.status} ${lead.note}`}
                filters={[
                  { key: 'status', label: '状态', value: (lead) => lead.status },
                  { key: 'market', label: '市场', value: (lead) => lead.market },
                  { key: 'platform', label: '平台', value: (lead) => lead.platform },
                ]}
                sorts={[
                  { id: 'new', label: '时间新到旧', compare: (left, right) => (right.created_at || '').localeCompare(left.created_at || '') },
                  { id: 'old', label: '时间旧到新', compare: (left, right) => (left.created_at || '').localeCompare(right.created_at || '') },
                  { id: 'score', label: '分数高到低', compare: (left, right) => right.quality_score - left.quality_score },
                ]}
                empty="这一路还没有线索。"
                render={(lead) => (
                <article className="grid items-center gap-2 rounded-xl border border-border p-3 sm:grid-cols-[auto_minmax(0,1fr)_auto]">
                  <input className="size-4" type="checkbox" checked={picked.includes(lead.id)} aria-label={`选择 ${lead.company}`} onChange={(event) => setPicked((currentIds) => event.target.checked ? [...currentIds, lead.id] : currentIds.filter((id) => id !== lead.id))} />
                  <span className="min-w-0 text-sm">
                    <span className="font-medium">{lead.company}</span>
                    <span className="mt-0.5 block truncate text-xs text-muted-foreground">{lead.email || '无邮箱'} · {lead.market} · {lead.platform} · {lead.quality_score}{lead.qualified ? '' : ' 未达标'} · {lead.status}</span>
                  </span>
                  <span className="grid grid-cols-2 gap-2">
                    <button type="button" className="h-9 rounded-lg border border-border px-3 text-sm" onClick={() => void run(() => api(`/leads/${lead.id}/signals`, { method: 'POST', body: JSON.stringify({ type: 'open' }) }).then(() => undefined))}>打开</button>
                    <button type="button" className="h-9 rounded-lg border border-border px-3 text-sm" onClick={() => setPop({
                      title: `赢单 · ${lead.company}`,
                      body: channel.id === 'raas' ? '这只改线索状态。结果分佣不认手点赢单，成交要等支付成功。' : '标记赢单后，若发生在送达后 14 天内，计入获客率。',
                      confirm: '确认赢单',
                      run: async () => {
                        await api(`/leads/${lead.id}/signals`, { method: 'POST', body: JSON.stringify({ type: 'won' }) })
                        setMessage(channel.id === 'raas' ? '已标记赢单。这一下不产生抽成。' : '已标记赢单。若发生在送达后 14 天内，计入获客率。')
                      },
                    })}>赢单</button>
                  </span>
                </article>
                )}
              />
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
                    body: JSON.stringify({ name: `${channel.code} ${new Date().toLocaleString('zh-CN')}`, lead_ids: picked, seed_analysis_id: seed || null, market_pack: TRADE_ROUTES[route].market_pack }),
                  })
                  setMessage('活动已创建。未批准不能发送。')
                })
              }}>用已选线索创建活动</button>
            </div>
            <ReachPicker value={reach} onChange={setReach} />
            <div className="mt-3">
              <ResultDesk
                items={campaigns}
                placeholder="搜索活动、状态或草稿"
                keywords={(campaign) => `${campaign.name} ${campaign.status} ${campaign.draft || ''}`}
                filters={[{ key: 'status', label: '状态', value: (campaign) => campaign.status }]}
                sorts={[
                  { id: 'new', label: '时间新到旧', compare: (left, right) => (right.created_at || right.id).localeCompare(left.created_at || left.id) },
                  { id: 'old', label: '时间旧到新', compare: (left, right) => (left.created_at || left.id).localeCompare(right.created_at || right.id) },
                  { id: 'name', label: '名称', compare: (left, right) => left.name.localeCompare(right.name, 'zh') },
                ]}
                empty="还没有触达活动。"
                render={(campaign) => (
                <article className="rounded-xl border border-border p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="truncate text-sm font-medium">{campaign.name}</h3>
                      <p className="text-xs text-muted-foreground">状态 {campaign.status}{campaign.draft ? ` · ${campaign.draft}` : ''}</p>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      <button type="button" className="h-9 rounded-lg border border-border px-3 text-sm" onClick={() => void run(() => api(`/campaigns/${campaign.id}/drafts`, { method: 'POST' }).then(() => setMessage('草稿已生成，等待批准。')))}>草稿</button>
                      <button type="button" className="h-9 rounded-lg border border-border px-3 text-sm" onClick={() => void run(() => api(`/campaigns/${campaign.id}/approve`, { method: 'POST' }).then(() => setMessage('已批准，并冻结受众快照。')))}>批准</button>
                      <button type="button" className="h-9 rounded-lg border border-border px-3 text-sm" onClick={() => setPop(reachSend(reach, `发送 · ${campaign.name}`, async () => {
                        const created = await api<{ job_id: string }>(`/campaigns/${campaign.id}/send`, { method: 'POST' })
                        const job = await waitJob(created.job_id)
                        if (job.status === 'failed') throw new Error(job.error?.message || '发送失败')
                        setMessage('邮箱发送任务完成。演示环境不会真实发信。')
                      }, setMessage))}>发送</button>
                    </div>
                  </div>
                </article>
                )}
              />
            </div>
          </div>
        )}
        {view === 'activation' && (
          <LifePanel
            title="冷客启动"
            reach={reach}
            onReach={setReach}
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
            onSend={(job) => setPop(reachSend(reach, '发送冷启', async () => {
              const created = await api<{ job_id: string }>(`/activation/jobs/${job.id}/send`, { method: 'POST' })
              const finished = await waitJob(created.job_id)
              if (finished.status === 'failed') throw new Error(finished.error?.message || '发送失败')
              setMessage('邮箱冷启已提交。演示环境不会真实发信。')
            }, setMessage))}
          />
        )}
        {view === 'recall' && (
          <div className="max-w-2xl">
            <h2 className="font-semibold">流失召回</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">打开过但没回复的线索，由规则进入召回。必须先批准才能发送。这里只说明规则。</p>
          </div>
        )}
        {view === 'ledger' && (
          <div className="max-w-2xl">
            <h2 className="font-semibold">{channel.id === 'raas' ? '结果分佣' : '分成入账'}</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">代理分成和 RaaS 抽成由服务端验签后入账。这里不收款。</p>
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

function reachSend(reach: ReachId, title: string, emailRun: () => Promise<void>, setMessage: (value: string) => void): Pop {
  const form = reachForms.find((item) => item.id === reach)
  if (reach !== 'email') {
    return {
      title: `${form?.name} · 占位`,
      body: `${form?.name}触达还没有接通。这里只保留入口，不会发出内容。`,
      confirm: '知道了',
      run: async () => setMessage(`${form?.name}仍是占位，没有发送。`),
    }
  }
  return {
    title,
    body: '邮箱走演示发送，不会真实发信。未批准时服务端会拒绝。',
    confirm: '确认发送',
    run: emailRun,
  }
}

function ReachPicker({ value, onChange }: { value: ReachId; onChange: (value: ReachId) => void }) {
  return (
    <div className="mt-3">
      <p className="text-xs text-muted-foreground">触达方式。邮箱是演示占位，短信、微信和电话只保留入口。</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {reachForms.map((item) => (
          <button key={item.id} type="button" className={`h-10 rounded-xl px-4 text-sm ${value === item.id ? 'bg-primary text-primary-foreground' : 'border border-border'}`} onClick={() => onChange(item.id)}>
            {item.name}{item.id === 'email' ? '' : ' · 占位'}
          </button>
        ))}
      </div>
    </div>
  )
}

function LifePanel({ title, jobs, busy, empty, reach, onReach, onScan, onApprove, onSend }: { title: string; jobs: LifeJob[]; busy: boolean; empty: string; reach: ReachId; onReach: (value: ReachId) => void; onScan?: () => void; onApprove: (id: string) => void; onSend: (job: LifeJob) => void }) {
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">{title}</h2>
        {onScan && <button type="button" disabled={busy} className="h-11 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground disabled:opacity-50" onClick={onScan}>规则扫描</button>}
      </div>
      <ReachPicker value={reach} onChange={onReach} />
      <div className="mt-3">
        <ResultDesk
          items={jobs}
          placeholder="搜索原因、状态或草稿"
          keywords={(job) => `${job.reason} ${job.status} ${job.draft}`}
          filters={[{ key: 'status', label: '状态', value: (job) => job.status }]}
          sorts={[
            { id: 'new', label: '时间新到旧', compare: (left, right) => (right.created_at || right.id).localeCompare(left.created_at || left.id) },
            { id: 'old', label: '时间旧到新', compare: (left, right) => (left.created_at || left.id).localeCompare(right.created_at || right.id) },
          ]}
          empty={empty}
          render={(job) => (
          <article className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border p-3 text-sm">
            <span className="min-w-0">
              <span>{job.reason} · {job.status}</span>
              <span className="mt-0.5 block truncate text-xs text-muted-foreground">{job.draft}</span>
            </span>
            <span className="grid grid-cols-2 gap-2">
              <button type="button" className="h-9 rounded-lg border border-border px-3 text-sm" onClick={() => onApprove(job.id)}>批准</button>
              <button type="button" className="h-9 rounded-lg border border-border px-3 text-sm" onClick={() => onSend(job)}>发送</button>
            </span>
          </article>
          )}
        />
      </div>
    </div>
  )
}
