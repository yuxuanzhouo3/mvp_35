'use client'

import { useEffect, useMemo, useState } from 'react'
import { PlatformMark } from '@/components/brand-marks'
import { api } from '@/lib/api'
import { tintForPlatform } from '@/lib/brand-tints'

const names: Record<string, string> = {
  amazon: '亚马逊',
  temu: 'Temu',
  walmart: '沃尔玛',
  taobao: '淘宝',
  pinduoduo: '拼多多',
  linkedin: 'LinkedIn',
  facebook: 'Facebook',
  wechat_mini: '微信',
  douyin: '抖音',
  xiaohongshu: '小红书',
  kuaishou: '快手',
  alibaba_com: '国际站',
  canton_fair: '广交会',
  global_sources: '环球资源',
  ciie: '进博会',
  online_expo: '其他展',
  qichacha: '企查查',
  tianyancha: '天眼查',
  qixin: '启信宝',
  agent_1: '代理1',
  agent_2: '代理2',
  agent_3: '代理3',
}

const fieldLabels: Record<string, string> = {
  client_id: 'Client ID',
  client_secret: 'Client Secret',
  corp_id: '企业 ID',
  contact_secret: '客户联系 Secret',
  follow_userid: '跟进人 userid',
  app_key: 'App Key',
  secret_key: 'Secret Key',
  token: 'Token',
  access_token: 'Access Token',
}

type ModeDef = { id: string; name: string; copy: string; platforms?: string[] }

const modesByChannel: Record<string, ModeDef[]> = {
  ecommerce: [
    { id: 'analyze', name: '分析订单', copy: '从订单找买家', platforms: ['amazon', 'walmart', 'taobao'] },
    { id: 'half', name: '半托管', copy: '平台接一部分', platforms: ['temu', 'taobao', 'pinduoduo'] },
    { id: 'full', name: '全托管', copy: '你只收钱', platforms: ['temu', 'pinduoduo', 'amazon'] },
  ],
  social: [
    { id: 'invent', name: 'AI 造热点', copy: '种草→表单→微信/邮箱/手机' },
    { id: 'remix', name: '复刻热点', copy: '改写→表单→微信/邮箱/手机' },
  ],
  expo: [
    { id: 'settle', name: '入驻展会', copy: '入驻后收意向与联系方式' },
    { id: 'follow', name: '询盘跟进', copy: '跟进询盘并补联系方式' },
  ],
  agency: [
    { id: 'directory', name: '搜集平台', copy: '整理代理商平台通讯录' },
    { id: 'outreach', name: '私联合约', copy: '联系一二級谈分销合约' },
  ],
  enrichment: [
    { id: 'search', name: '法人检索', copy: '搜全国公司法人通信信息' },
    { id: 'merge', name: '客源汇聚', copy: '合并线索并补通信方式' },
  ],
}

type Account = {
  platform: string
  status: string
  mode: string
  mode_label: string
  authorize_url: string
  missing: string
  needs_credentials?: boolean
  credential_fields?: string[]
  has_token?: boolean
}

export function ChannelLogin({ channel, platforms }: { channel: string; platforms: string[] }) {
  const channelModes = modesByChannel[channel] || []
  const [mode, setMode] = useState(channelModes[0]?.id || '')
  const [accounts, setAccounts] = useState<Account[]>([])
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState('')
  const [pasteFor, setPasteFor] = useState('')
  const [fields, setFields] = useState<string[]>([])
  const [values, setValues] = useState<Record<string, string>>({})

  useEffect(() => {
    setMode(channelModes[0]?.id || '')
  }, [channel])

  const visible = useMemo(() => {
    if (channel !== 'ecommerce') return platforms
    const picked = new Set<string>([...(channelModes.find((item) => item.id === mode)?.platforms || [])])
    return platforms.filter((platform) => picked.has(platform))
  }, [channel, mode, platforms, channelModes])

  async function reload() {
    const data = await api<{ items: Account[] }>(`/channel-accounts?channel=${encodeURIComponent(channel)}`)
    setAccounts(data.items)
  }

  useEffect(() => {
    reload().catch((reason: Error) => setNotice(reason.message))
  }, [channel])

  function row(platform: string) {
    return accounts.find((item) => item.platform === platform)
  }

  async function login(platform: string, credentials?: Record<string, string>) {
    setBusy(platform)
    setNotice('')
    try {
      const saved = await api<Account>('/channel-accounts/login', {
        method: 'POST',
        body: JSON.stringify({
          channel,
          platform,
          mode,
          credentials: credentials || {},
        }),
      })
      if (saved.authorize_url) {
        window.location.assign(saved.authorize_url)
        return
      }
      if (saved.needs_credentials && (saved.credential_fields || []).length > 0 && !credentials) {
        setPasteFor(platform)
        setFields(saved.credential_fields || [])
        setValues({})
        if (saved.missing) setNotice(`${names[platform] || platform}：${saved.missing}`)
        return
      }
      if (saved.missing) setNotice(`${names[platform] || platform}：${saved.missing}`)
      setPasteFor('')
      await reload()
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : '登录失败')
    } finally {
      setBusy('')
    }
  }

  async function submitPaste() {
    if (!pasteFor) return
    const credentials: Record<string, string> = {}
    for (const field of fields) {
      const value = (values[field] || '').trim()
      if (!value) {
        setNotice(`请填写 ${fieldLabels[field] || field}`)
        return
      }
      credentials[field] = value
    }
    await login(pasteFor, credentials)
  }

  const modeHintName = (account?: Account) => {
    const id = account?.mode || mode
    return channelModes.find((item) => item.id === id)?.name || account?.mode_label || ''
  }

  return (
    <div className="mb-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="text-sm font-semibold">登录平台账号</h2>
        <p className="text-xs text-muted-foreground">先选做法，再登录</p>
      </div>
      {channelModes.length > 0 && (
        <div className={`mt-2 grid gap-1 ${channelModes.length >= 3 ? 'grid-cols-3' : 'grid-cols-2'}`}>
          {channelModes.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={mode === item.id}
              className={`rounded-lg border px-1.5 py-1.5 text-left transition md:px-2 ${mode === item.id ? 'border-primary bg-primary/10 ring-1 ring-primary/20' : 'border-border bg-background hover:bg-muted/60'}`}
              onClick={() => setMode(item.id)}
            >
              <span className="block text-[11px] font-medium leading-tight md:text-xs">{item.name}</span>
              <span className="mt-0.5 hidden text-[10px] leading-tight text-muted-foreground md:block">{item.copy}</span>
            </button>
          ))}
        </div>
      )}
      <div className="mt-2 grid grid-cols-1 gap-1.5 min-[360px]:grid-cols-2 sm:grid-cols-3">
        {visible.map((platform) => {
          const account = row(platform)
          const connected = account?.status === 'connected'
          const tint = tintForPlatform(platform)
          const hint = modeHintName(account)
          return (
            <div key={`${mode}-${platform}`} className={`flex items-center gap-1.5 rounded-lg border px-2 py-1.5 ${tint.card}`}>
              <PlatformMark platform={platform} className="size-7" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-medium leading-tight">{names[platform] || platform}</p>
                <p className="truncate text-[10px] leading-tight text-muted-foreground">
                  {connected ? (account?.has_token ? '已登录·可获客' : '已连接') : '未登录'}
                  {hint ? ` · ${hint}` : ''}
                </p>
              </div>
              <button
                type="button"
                disabled={busy === platform || !mode}
                className={`h-7 shrink-0 rounded-md px-2 text-[11px] font-medium text-white disabled:opacity-50 ${tint.button}`}
                onClick={() => void login(platform)}
              >
                {connected ? '重登' : '登录'}
              </button>
            </div>
          )
        })}
      </div>
      {pasteFor && (
        <div className="mt-2 space-y-1.5 rounded-lg border border-border bg-muted/30 p-2">
          <p className="text-xs font-medium">{names[pasteFor] || pasteFor} · 粘贴密钥登录</p>
          {fields.map((field) => (
            <input
              key={field}
              type="password"
              autoComplete="off"
              placeholder={fieldLabels[field] || field}
              value={values[field] || ''}
              className="h-8 w-full rounded-md border border-border bg-background px-2 text-xs"
              onChange={(event) => setValues((current) => ({ ...current, [field]: event.target.value }))}
            />
          ))}
          <div className="flex gap-2">
            <button type="button" className="h-8 rounded-md bg-primary px-3 text-xs text-primary-foreground" onClick={() => void submitPaste()}>
              保存并登录
            </button>
            <button type="button" className="h-8 rounded-md border border-border px-3 text-xs" onClick={() => setPasteFor('')}>
              取消
            </button>
          </div>
        </div>
      )}
      {notice && <p className="mt-1.5 text-xs text-destructive">{notice}</p>}
    </div>
  )
}
