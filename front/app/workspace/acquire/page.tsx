'use client'

import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { api, waitJob } from '@/lib/api'

const channels = [
  { id: 'ecommerce', label: 'B1 电商', platforms: ['amazon', 'temu', 'walmart', 'taobao', 'pinduoduo'] },
  { id: 'social', label: 'B2 社交', platforms: ['linkedin', 'facebook', 'wechat_mini', 'douyin', 'xiaohongshu', 'kuaishou'] },
  { id: 'expo', label: 'B3 展会', platforms: ['online_expo'] },
  { id: 'agency', label: 'B4 代理', platforms: ['agent_1', 'agent_2', 'agent_3'] },
  { id: 'enrichment', label: 'B5 大数据', platforms: ['qichacha', 'tianyancha'] },
  { id: 'geo_seo', label: 'B6 GEO/SEO', platforms: ['landing'] },
  { id: 'content_dh', label: 'B7 内容/数智人', platforms: ['content_factory', 'digital_human_placeholder', 'offline_qr'] },
  { id: 'cross_border', label: 'B8 跨境元素', platforms: ['cn_us', 'cn_hk', 'cn_au', 'domestic'] },
  { id: 'raas', label: 'B9 RaaS', platforms: ['site_success', 'app_account'] },
]

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

export default function AcquirePage() {
  return <Suspense fallback={<p className="text-sm text-muted-foreground">加载获客工作台…</p>}><AcquireDesk /></Suspense>
}

function AcquireDesk() {
  const seed = useSearchParams().get('seed_analysis_id') || ''
  const [channel, setChannel] = useState(channels[0])
  const [platform, setPlatform] = useState(channels[0].platforms[0])
  const [leads, setLeads] = useState<Lead[]>([])
  const [picked, setPicked] = useState<string[]>([])
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [activeId, setActiveId] = useState('')
  const [activation, setActivation] = useState<LifeJob[]>([])
  const [recall, setRecall] = useState<LifeJob[]>([])
  const [amount, setAmount] = useState('1500')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function reload() {
    const [leadData, campaignData, activationData, recallData] = await Promise.all([
      api<{ items: Lead[] }>(`/leads${seed ? `?seed_analysis_id=${seed}` : ''}`),
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
    reload().catch((reason: Error) => setError(reason.message))
  }, [seed])

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

  const active = campaigns.find((item) => item.id === activeId)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <span className="eyebrow">路径 B · 九路获客</span>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">线索、触达、成交与召回</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
          九路进入同一线索池。触达顺序是生成草稿、人工批准、再发送。冷启和召回由规则入队。B9 抽成单独入账，不混进普通获客率。
          {seed ? ` 当前种子报告 ${seed}。` : ''}
        </p>
      </div>
      {error && <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
      {message && <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{message}</p>}

      <section className="rounded-2xl border border-border bg-card p-5">
        <h2 className="font-semibold">发现线索</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {channels.map((item) => (
            <button key={item.id} className={`rounded-lg px-2.5 py-1.5 text-xs ${channel.id === item.id ? 'bg-primary text-primary-foreground' : 'border border-border'}`} onClick={() => { setChannel(item); setPlatform(item.platforms[0]) }}>{item.label}</button>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <select className="rounded-lg border border-border bg-background px-2 py-2 text-sm" value={platform} onChange={(event) => setPlatform(event.target.value)} aria-label="平台">
            {channel.platforms.map((item) => <option key={item}>{item}</option>)}
          </select>
          <button disabled={busy} className="rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" onClick={() => {
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
        </div>
        {platform === 'digital_human_placeholder' && <p className="mt-2 text-xs text-muted-foreground">数智人 DEMO 为占位演示，不购买 10 小时包。</p>}
      </section>

      <section className="overflow-hidden rounded-2xl border border-border bg-card">
        <table className="data-table">
          <thead><tr><th></th><th>公司</th><th>通道</th><th>分数</th><th>状态</th><th>动作</th></tr></thead>
          <tbody>
            {leads.map((lead) => (
              <tr key={lead.id}>
                <td><input type="checkbox" checked={picked.includes(lead.id)} aria-label={`选择 ${lead.company}`} onChange={(event) => setPicked((current) => event.target.checked ? [...current, lead.id] : current.filter((id) => id !== lead.id))} /></td>
                <td>{lead.company}<div className="text-xs text-muted-foreground">{lead.email || '无邮箱'} · {lead.market}{lead.note ? ` · ${lead.note}` : ''}</div></td>
                <td>{lead.source_channel}/{lead.platform}{lead.exclude_from_ar ? ' · 不计入 AR' : ''}</td>
                <td>{lead.quality_score}{lead.qualified ? '' : ' · 未达标'}</td>
                <td>{lead.status}</td>
                <td className="flex gap-3">
                  <button className="text-sm text-primary" onClick={() => void run(() => api(`/leads/${lead.id}/signals`, { method: 'POST', body: JSON.stringify({ type: 'open' }) }).then(() => undefined))}>打开</button>
                  <button className="text-sm text-primary" onClick={() => void run(() => api(`/leads/${lead.id}/signals`, { method: 'POST', body: JSON.stringify({ type: 'won' }) }).then(() => setMessage('已标记赢单。若发生在送达后 14 天内，计入获客率。')))}>赢单</button>
                </td>
              </tr>
            ))}
            {leads.length === 0 && <tr><td colSpan={6} className="text-muted-foreground">线索池是空的。</td></tr>}
          </tbody>
        </table>
      </section>

      <section className="rounded-2xl border border-border bg-card p-5">
        <h2 className="font-semibold">触达：生成 → 批准 → 发送</h2>
        <button disabled={busy || picked.length === 0} className="mt-3 rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50" onClick={() => {
          void run(async () => {
            const campaign = await api<Campaign>('/campaigns', {
              method: 'POST',
              body: JSON.stringify({ name: `获客 ${new Date().toLocaleString('zh-CN')}`, lead_ids: picked, seed_analysis_id: seed || null, market_pack: 'cn_us' }),
            })
            setActiveId(campaign.id)
            setMessage('活动已创建，请生成草稿。未批准不能发送。')
          })
        }}>用已选线索创建活动</button>
        <div className="mt-4 flex flex-col gap-3">
          {campaigns.map((campaign) => (
            <article key={campaign.id} className={`rounded-xl border p-3 ${activeId === campaign.id ? 'border-primary' : 'border-border'}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="font-medium">{campaign.name}</h3>
                  <p className="text-xs text-muted-foreground">状态 {campaign.status}{campaign.seed_analysis_id ? ` · 种子 ${campaign.seed_analysis_id}` : ''}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button className="rounded-lg border border-border px-2 py-1 text-xs" onClick={() => void run(() => api(`/campaigns/${campaign.id}/drafts`, { method: 'POST' }).then(() => setMessage('草稿已生成，等待批准。')))}>生成草稿</button>
                  <button className="rounded-lg border border-border px-2 py-1 text-xs" onClick={() => void run(() => api(`/campaigns/${campaign.id}/approve`, { method: 'POST' }).then(() => setMessage('已批准，并冻结受众快照。')))}>批准</button>
                  <button className="rounded-lg border border-border px-2 py-1 text-xs" onClick={() => void run(async () => {
                    const created = await api<{ job_id: string }>(`/campaigns/${campaign.id}/send`, { method: 'POST' })
                    const job = await waitJob(created.job_id)
                    if (job.status === 'failed') throw new Error(job.error?.message || '发送失败')
                    setMessage('发送任务完成。演示环境使用 SES mock，不会真实发信。')
                  })}>发送</button>
                </div>
              </div>
              {campaign.draft && <p className="mt-2 text-sm leading-6 text-muted-foreground">{campaign.draft}</p>}
            </article>
          ))}
        </div>
        {active?.draft && <p className="sr-only">当前草稿 {active.draft}</p>}
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <LifeList title="冷客启动" jobs={activation} busy={busy} onScan={() => void run(async () => {
          const created = await api<{ job_id: string }>('/lifecycle/scan', { method: 'POST' })
          const job = await waitJob(created.job_id)
          if (job.status === 'failed') throw new Error(job.error?.message || '扫描失败')
          setMessage('规则扫描完成。合格且从未触达的线索进入冷启，打开后未回复的线索进入召回。')
        })} onApprove={(id) => void run(() => api(`/activation/jobs/${id}/approve`, { method: 'POST' }).then(() => undefined))} onSend={(id) => void run(async () => {
          const created = await api<{ job_id: string }>(`/activation/jobs/${id}/send`, { method: 'POST' })
          const job = await waitJob(created.job_id)
          if (job.status === 'failed') throw new Error(job.error?.message || '发送失败')
        })} />
        <LifeList title="流失召回" jobs={recall} busy={busy} onScan={() => undefined} onApprove={(id) => void run(() => api(`/recall/jobs/${id}/approve`, { method: 'POST' }).then(() => undefined))} onSend={(id) => void run(async () => {
          const created = await api<{ job_id: string }>(`/recall/jobs/${id}/send`, { method: 'POST' })
          const job = await waitJob(created.job_id)
          if (job.status === 'failed') throw new Error(job.error?.message || '发送失败')
        })} />
      </section>

      <section className="rounded-2xl border border-border bg-card p-5">
        <h2 className="font-semibold">代理分成与 RaaS 抽成</h2>
        <p className="mt-2 text-xs leading-6 text-muted-foreground">金额是整数分。服务端先验签，同一幂等键不会重复入账。浏览器拿不到签名密钥。</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input className="w-32 rounded-lg border border-border px-2 py-2 text-sm" value={amount} onChange={(event) => setAmount(event.target.value)} aria-label="金额分" />
          <button className="rounded-lg border border-border px-3 py-2 text-sm" onClick={() => void postLedger('agency_commission', '/billing/agency/commissions')}>代理分成入账</button>
          <button className="rounded-lg border border-border px-3 py-2 text-sm" onClick={() => void postLedger('raas_fee', '/billing/raas/commissions')}>RaaS 抽成入账</button>
        </div>
      </section>
    </div>
  )

  async function postLedger(subject: string, path: string) {
    await run(async () => {
      const fen = Number(amount)
      if (!Number.isInteger(fen) || fen <= 0) throw new Error('金额必须是正整数分')
      const idempotencyKey = `${subject}-${Date.now()}`
      const signed = await api<{ signature: string }>('/dev/ledger-signature', {
        method: 'POST',
        body: JSON.stringify({ idempotency_key: idempotencyKey, amount_fen: fen, subject }),
      })
      await api(path, {
        method: 'POST',
        body: JSON.stringify({ amount_fen: fen, idempotency_key: idempotencyKey, signature: signed.signature, channel_account_id: 'agent_1' }),
      })
      setMessage(subject === 'raas_fee' ? 'RaaS 抽成已入账，不会计入普通获客率。' : '代理分成已入账。')
    })
  }
}

function LifeList({ title, jobs, busy, onScan, onApprove, onSend }: { title: string; jobs: LifeJob[]; busy: boolean; onScan: () => void; onApprove: (id: string) => void; onSend: (id: string) => void }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">{title}</h2>
        {title === '冷客启动' && <button disabled={busy} className="text-sm text-primary" onClick={onScan}>规则扫描</button>}
      </div>
      <div className="mt-3 flex flex-col gap-2">
        {jobs.map((job) => (
          <div key={job.id} className="rounded-xl border border-border p-3 text-sm">
            <p>{job.reason} · {job.status}</p>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">{job.draft}</p>
            <div className="mt-2 flex gap-2">
              <button className="text-xs text-primary" onClick={() => onApprove(job.id)}>批准</button>
              <button className="text-xs text-primary" onClick={() => onSend(job.id)}>发送</button>
            </div>
          </div>
        ))}
        {jobs.length === 0 && <p className="text-xs text-muted-foreground">暂无任务。</p>}
      </div>
    </div>
  )
}
