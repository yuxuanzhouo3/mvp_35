'use client'

import { useEffect, useState } from 'react'
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

const modes = [
  { id: 'analyze', name: '分析订单', copy: '从订单找买家' },
  { id: 'half', name: '半托管', copy: '平台接一部分' },
  { id: 'full', name: '全托管', copy: '你只收钱' },
]

type Account = {
  platform: string
  status: string
  mode: string
  mode_label: string
  authorize_url: string
  missing: string
}

export function ChannelLogin({ channel, platforms }: { channel: string; platforms: string[] }) {
  const [mode, setMode] = useState('analyze')
  const [accounts, setAccounts] = useState<Account[]>([])
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState('')

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

  async function login(platform: string) {
    setBusy(platform)
    setNotice('')
    try {
      const saved = await api<Account>('/channel-accounts/login', {
        method: 'POST',
        body: JSON.stringify({ channel, platform, mode: channel === 'ecommerce' ? mode : '' }),
      })
      if (saved.authorize_url) {
        window.location.assign(saved.authorize_url)
        return
      }
      if (saved.missing) setNotice(`${names[platform] || platform}：${saved.missing}`)
      await reload()
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : '登录失败')
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="mb-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="text-sm font-semibold">登录平台账号</h2>
        <p className="text-xs text-muted-foreground">获客下一步再接</p>
      </div>
      {channel === 'ecommerce' && (
        <div className="mt-2 grid grid-cols-3 gap-1.5">
          {modes.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`rounded-lg border px-2 py-1.5 text-left ${mode === item.id ? 'border-blue-600 bg-blue-50' : 'border-border bg-background'}`}
              onClick={() => setMode(item.id)}
            >
              <span className="block text-xs font-medium leading-tight">{item.name}</span>
              <span className="mt-0.5 block text-[10px] leading-tight text-muted-foreground">{item.copy}</span>
            </button>
          ))}
        </div>
      )}
      <div className="mt-2 grid grid-cols-2 gap-1.5 sm:grid-cols-3 md:grid-cols-5">
        {platforms.map((platform) => {
          const account = row(platform)
          const connected = account?.status === 'connected'
          const tint = tintForPlatform(platform)
          return (
            <div key={platform} className={`flex items-center gap-1.5 rounded-lg border px-2 py-1.5 ${tint.card}`}>
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-medium leading-tight">{names[platform] || platform}</p>
                <p className="truncate text-[10px] leading-tight text-muted-foreground">{connected ? '已登录' : '未登录'}</p>
              </div>
              <button
                type="button"
                disabled={busy === platform}
                className={`h-7 shrink-0 rounded-md px-2 text-[11px] font-medium text-white disabled:opacity-50 ${tint.button}`}
                onClick={() => void login(platform)}
              >
                {connected ? '重登' : '登录'}
              </button>
            </div>
          )
        })}
      </div>
      {notice && <p className="mt-1.5 text-xs text-destructive">{notice}</p>}
    </div>
  )
}
