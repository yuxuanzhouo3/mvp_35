'use client'

import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import Link from 'next/link'
import { ChevronDown, CreditCard, Gift, LogOut, Settings, User } from 'lucide-react'
import { api } from '@/lib/api'
import { readAppearance, writeAppearance, type Appearance } from '@/lib/appearance'

type Profile = {
  user: { id?: string; display_name?: string; username?: string; email?: string; phone?: string; role?: string }
  tenant: { plan_id?: string; name?: string }
  role?: string
}

type Person = { id: string; name: string; email_masked?: string | null; created_at?: string | null; via_name?: string }
type InviteEvent = {
  invitee_name: string
  link: string
  invited_at?: string | null
  paid_at?: string | null
  paid_fen: number
  reward_fen: number
}
type CashRequest = { id: string; kind?: string; amount_fen: number; status: string; requested_at?: string | null; due_at?: string | null; paid_at?: string | null }
type Coupon = { id: string; label: string; rate: string; status: string }
type Invite = {
  invite_code: string
  share_path: string
  used_by: Person[]
  invited_later: Person[]
  paid_fen: number
  owed_fen: number
  discount_fen: number
  events: InviteEvent[]
  cash_requests: CashRequest[]
  draw_chances: number
  login_streak: number
  coupons: Coupon[]
}

const planLabel: Record<string, string> = { free: '免费', growth: '成长', scale: '规模' }

function yuan(fen: number) {
  return `¥${(fen / 100).toFixed(2)}`
}

function when(value?: string | null) {
  if (!value) return '—'
  return value.replace('T', ' ').slice(0, 16)
}

const cashStatus: Record<string, string> = { paid: '已打款', scheduled: '待打款', pending: '待打款' }
const cashKind: Record<string, string> = { invite: '邀请奖励', draw: '抽奖', streak: '连续登录' }

function SettingRow({ label, hint, children }: { label: string; hint: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background px-3 py-2">
      <div className="min-w-0">
        <p className="text-sm">{label}</p>
        <p className="hidden text-xs text-muted-foreground sm:block">{hint}</p>
      </div>
      <div className="w-32 shrink-0 sm:w-40">{children}</div>
    </div>
  )
}

export function UserMenu({ name, onLogout }: { name: string; onLogout: () => void }) {
  const [open, setOpen] = useState(false)
  const [dialog, setDialog] = useState<'settings' | 'invite' | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [invite, setInvite] = useState<Invite | null>(null)
  const [inviteError, setInviteError] = useState('')
  const [notice, setNotice] = useState('')
  const [look, setLook] = useState<Appearance>({ theme: 'light', font: 'default', fontSize: '16', density: 'comfortable', ads: true })
  const [origin, setOrigin] = useState('')
  const box = useRef<HTMLDivElement>(null)
  const menu = useRef<HTMLDivElement>(null)
  const [spot, setSpot] = useState({ top: 64, right: 12, dock: 92 })

  useEffect(() => {
    const saved = readAppearance()
    setLook(saved)
    setOrigin(window.location.origin)
    writeAppearance(saved)
  }, [])

  useEffect(() => {
    function close(event: MouseEvent) {
      const target = event.target as Node
      if (box.current?.contains(target) || menu.current?.contains(target)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  useEffect(() => {
    if (!dialog) return
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setDialog(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dialog])

  function loadProfile() {
    api<Profile>('/users/me').then(setProfile).catch(() => undefined)
  }

  function toggleMenu() {
    const rect = box.current?.getBoundingClientRect()
    if (rect) {
      const dock = window.matchMedia('(max-width: 767px)').matches ? 92 : 16
      setSpot({ top: rect.bottom + 8, right: Math.max(12, window.innerWidth - rect.right), dock })
    }
    setOpen((current) => {
      if (!current) loadProfile()
      return !current
    })
  }

  function choose(next: 'settings' | 'invite') {
    setOpen(false)
    setNotice('')
    setDialog(next)
    if (next === 'invite') {
      setInvite(null)
      setInviteError('')
      api<Invite>('/users/me/invite')
        .then(setInvite)
        .catch((reason) => setInviteError(reason instanceof Error ? reason.message : '邀请链接暂时取不到'))
    }
  }

  function saveLook(patch: Partial<Appearance>) {
    const next = { ...look, ...patch }
    setLook(next)
    writeAppearance(next)
  }

  async function claimCash() {
    setNotice('')
    try {
      await api('/users/me/invite/cash', { method: 'POST' })
      const fresh = await api<Invite>('/users/me/invite')
      setInvite(fresh)
      setNotice('已申请兑现。现金在 5 个工作日内打出，周末不计入。')
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : '申请失败')
    }
  }

  async function drawOnce() {
    setNotice('')
    try {
      const result = await api<{ amount_fen: number; draw_chances: number }>('/users/me/draw', { method: 'POST' })
      const fresh = await api<Invite>('/users/me/invite')
      setInvite(fresh)
      setNotice(result.amount_fen > 0 ? `抽中 ${yuan(result.amount_fen)}，将在 5 个工作日内打款。` : '这次没有抽中现金。')
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : '抽奖失败')
    }
  }

  async function copyLink() {
    if (!invite) return
    const link = `${window.location.origin}${invite.share_path}`
    try {
      await navigator.clipboard.writeText(link)
      setNotice('邀请链接已复制')
    } catch {
      setNotice(link)
    }
  }

  const displayName = profile?.user.display_name || profile?.user.username || name || '账号'
  const contact = profile?.user.email || profile?.user.phone || profile?.user.username || ''
  const plan = planLabel[profile?.tenant.plan_id || ''] || profile?.tenant.plan_id || '免费'
  const item = 'flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm hover:bg-muted'

  return (
    <div className="relative" ref={box}>
      <button
        type="button"
        className="inline-flex h-9 min-w-0 max-w-[4.25rem] items-center gap-1 rounded-lg border border-border bg-background px-1.5 text-sm text-foreground hover:bg-muted sm:max-w-[11rem] sm:gap-1.5 sm:px-2.5"
        onClick={toggleMenu}
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <User className="hidden size-4 shrink-0 text-muted-foreground sm:block" />
        <span className="truncate">{displayName}</span>
        <ChevronDown className="hidden size-3.5 shrink-0 text-muted-foreground sm:block" />
      </button>
      {open && createPortal(
        <div
          ref={menu}
          className="fixed z-[80] w-[min(16rem,calc(100vw-1.5rem))] overflow-y-auto overscroll-contain rounded-xl border border-blue-100 bg-card p-1 text-sm shadow-lg"
          style={{ top: spot.top, right: spot.right, maxHeight: `min(18rem, calc(100dvh - ${spot.top}px - ${spot.dock}px - env(safe-area-inset-bottom)))` }}
          role="menu"
        >
          <div className="rounded-lg px-2.5 py-1.5">
            <p className="truncate text-sm font-medium">{displayName}</p>
            <p className="truncate text-xs text-muted-foreground">{contact || plan}</p>
          </div>
          <div className="my-1 h-px bg-border" />
          <Link href="/workspace/billing" className={item} onClick={() => setOpen(false)}>
            <CreditCard className="size-4 text-muted-foreground" />
            账单
          </Link>
          <button type="button" className={item} onClick={() => choose('settings')}>
            <Settings className="size-4 text-muted-foreground" />
            界面设置
          </button>
          <button type="button" className={item} onClick={() => choose('invite')}>
            <Gift className="size-4 text-muted-foreground" />
            邀请
          </button>
          <div className="my-1 h-px bg-border" />
          <button type="button" className={item} onClick={onLogout}>
            <LogOut className="size-4 text-muted-foreground" />
            退出登录
          </button>
        </div>,
        document.body,
      )}
      {dialog && createPortal(
        <div className="fixed inset-0 z-[80] flex items-end justify-center bg-black/45 p-3 pb-[calc(5rem+env(safe-area-inset-bottom))] md:items-center md:p-4 md:pb-4" onClick={() => setDialog(null)}>
          <div className={`w-full overflow-y-auto overscroll-contain rounded-2xl border border-blue-100 bg-card p-4 shadow-2xl md:max-h-[86vh] md:p-5 ${dialog === 'invite' ? 'max-h-[min(24rem,calc(100dvh-8rem-env(safe-area-inset-bottom)))] max-w-3xl' : 'max-h-[min(20rem,calc(100dvh-8rem-env(safe-area-inset-bottom)))] max-w-lg'}`} onClick={(event) => event.stopPropagation()} role="dialog">
            {dialog === 'settings' && (
              <>
                <h2 className="text-lg font-semibold">界面设置</h2>
                <div className="mt-3 rounded-lg border border-border px-3 py-3">
                  <p className="text-sm font-medium">{displayName}</p>
                  <p className="text-xs text-muted-foreground">{contact || '未绑定邮箱或手机'}</p>
                  <p className="mt-2 text-xs text-muted-foreground">Premium Pro · {plan}{profile?.tenant.name ? ` · ${profile.tenant.name}` : ''}</p>
                </div>
                <div className="mt-3 space-y-2">
                  <SettingRow label="主题" hint="工作台页面的浅色或深色">
                    <select className="h-9 w-full rounded-lg border border-border bg-card px-2 text-sm" value={look.theme} onChange={(event) => saveLook({ theme: event.target.value as Appearance['theme'] })}>
                      <option value="light">浅色</option>
                      <option value="dark">深色</option>
                      <option value="system">跟随系统</option>
                    </select>
                  </SettingRow>
                  <SettingRow label="字号" hint="页面文字大小">
                    <select className="h-9 w-full rounded-lg border border-border bg-card px-2 text-sm" value={look.fontSize} onChange={(event) => saveLook({ fontSize: event.target.value as Appearance['fontSize'] })}>
                      <option value="14">14px</option>
                      <option value="16">16px</option>
                      <option value="18">18px</option>
                    </select>
                  </SettingRow>
                  <SettingRow label="字体" hint="正文使用的字体">
                    <select className="h-9 w-full rounded-lg border border-border bg-card px-2 text-sm" value={look.font} onChange={(event) => saveLook({ font: event.target.value as Appearance['font'] })}>
                      <option value="default">默认</option>
                      <option value="serif">衬线</option>
                      <option value="mono">等宽</option>
                    </select>
                  </SettingRow>
                  <SettingRow label="密度" hint="舒适或更紧凑的字号">
                    <select className="h-9 w-full rounded-lg border border-border bg-card px-2 text-sm" value={look.density} onChange={(event) => saveLook({ density: event.target.value as Appearance['density'] })}>
                      <option value="comfortable">舒适</option>
                      <option value="compact">紧凑</option>
                    </select>
                  </SettingRow>
                  <SettingRow label="广告" hint="工作台里的推广位">
                    <button type="button" className="h-9 w-full rounded-lg border border-border text-sm" onClick={() => saveLook({ ads: !look.ads })}>{look.ads ? '显示中，点击关闭' : '已关闭，点击打开'}</button>
                  </SettingRow>
                  <SettingRow label="账单与订阅" hint="套餐、支付和发票">
                    <Link href="/workspace/billing" className="inline-flex h-9 w-full items-center justify-center rounded-lg border border-border text-sm" onClick={() => setDialog(null)}>打开账单</Link>
                  </SettingRow>
                  <SettingRow label="隐私" hint="登录状态只保存在这台浏览器">
                    <button type="button" className="h-9 w-full rounded-lg border border-border text-sm" onClick={onLogout}>退出登录</button>
                  </SettingRow>
                  <SettingRow label="支持" hint="问题发到公司邮箱">
                    <a className="inline-flex h-9 w-full items-center justify-center rounded-lg border border-border text-sm" href="mailto:pickglobal@yeah.net">pickglobal@yeah.net</a>
                  </SettingRow>
                </div>
              </>
            )}
            {dialog === 'invite' && (
              <>
                <h2 className="text-lg font-semibold">邀请</h2>
                <p className="mt-1 text-sm text-muted-foreground">好友用这条链接注册。付费后奖励按 10% 先留在账户里当优惠，申请兑现后 5 个工作日内打现金。</p>
                <div className="mt-4 grid gap-3 sm:grid-cols-[12rem_minmax(0,1fr)]">
                  <div className="rounded-xl border border-border bg-muted/40 p-3">
                    <p className="text-xs text-muted-foreground">邀请码</p>
                    <p className="mt-1 font-mono text-base">{invite?.invite_code || (inviteError ? '暂时取不到' : '正在生成…')}</p>
                  </div>
                  <div className="rounded-xl border border-border bg-muted/40 p-3">
                    <p className="text-xs text-muted-foreground">邀请链接</p>
                    <p className="mt-1 break-all font-mono text-xs">{invite ? `${origin}${invite.share_path}` : ''}</p>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                  <p className="rounded-lg border border-border px-3 py-2">已邀请 <span className="font-medium">{invite?.used_by.length ?? 0}</span></p>
                  <p className="rounded-lg border border-border px-3 py-2">再邀请 <span className="font-medium">{invite?.invited_later.length ?? 0}</span></p>
                  <p className="rounded-lg border border-border px-3 py-2">好友付款 <span className="font-medium">{yuan(invite?.paid_fen ?? 0)}</span></p>
                  <p className="rounded-lg border border-border px-3 py-2">可兑现 <span className="font-medium">{yuan(invite?.discount_fen ?? 0)}</span></p>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">连续登录 {invite?.login_streak ?? 0} 天。满 7 天 1 次抽奖，满 14 天再加 2 次，满 30 天奖励现金。可抽 {invite?.draw_chances ?? 0} 次。</p>
                <h3 className="mt-5 text-sm font-medium">被邀请人</h3>
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full min-w-[32rem] text-left text-sm">
                    <thead className="text-xs text-muted-foreground">
                      <tr><th className="py-2 pr-3 font-medium">姓名</th><th className="py-2 pr-3 font-medium">邮箱</th><th className="py-2 font-medium">邀请日期</th></tr>
                    </thead>
                    <tbody>
                      {(invite?.used_by.length ? invite.used_by : []).map((person) => (
                        <tr key={person.id} className="border-t border-border">
                          <td className="py-2 pr-3">{person.name || '用户'}</td>
                          <td className="py-2 pr-3 text-muted-foreground">{person.email_masked || '—'}</td>
                          <td className="py-2">{when(person.created_at)}</td>
                        </tr>
                      ))}
                      {invite && invite.used_by.length === 0 && <tr><td className="py-3 text-muted-foreground" colSpan={3}>还没有人通过这条链接注册。</td></tr>}
                    </tbody>
                  </table>
                </div>
                <h3 className="mt-5 text-sm font-medium">付款与奖励</h3>
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full min-w-[40rem] text-left text-sm">
                    <thead className="text-xs text-muted-foreground">
                      <tr>
                        <th className="py-2 pr-3 font-medium">被邀请人</th>
                        <th className="py-2 pr-3 font-medium">邀请日期</th>
                        <th className="py-2 pr-3 font-medium">付款日期</th>
                        <th className="py-2 pr-3 font-medium">付款</th>
                        <th className="py-2 font-medium">奖励</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(invite?.events || []).map((event, index) => (
                        <tr key={`${event.invitee_name}-${event.paid_at || event.invited_at}-${index}`} className="border-t border-border">
                          <td className="py-2 pr-3">{event.invitee_name || '用户'}</td>
                          <td className="py-2 pr-3">{when(event.invited_at)}</td>
                          <td className="py-2 pr-3">{when(event.paid_at)}</td>
                          <td className="py-2 pr-3">{event.paid_fen > 0 ? yuan(event.paid_fen) : '未付款'}</td>
                          <td className="py-2">{event.reward_fen > 0 ? yuan(event.reward_fen) : '—'}</td>
                        </tr>
                      ))}
                      {invite && invite.events.length === 0 && <tr><td className="py-3 text-muted-foreground" colSpan={5}>还没有付款记录。</td></tr>}
                    </tbody>
                  </table>
                </div>
                {invite && invite.invited_later.length > 0 && (
                  <>
                    <h3 className="mt-5 text-sm font-medium">他们再邀请的人</h3>
                    <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                      {invite.invited_later.map((person) => (
                        <li key={person.id}>{person.name || '用户'}{person.via_name ? ` · 来自 ${person.via_name}` : ''} · {when(person.created_at)}</li>
                      ))}
                    </ul>
                  </>
                )}
                <h3 className="mt-5 text-sm font-medium">兑现记录</h3>
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full min-w-[36rem] text-left text-sm">
                    <thead className="text-xs text-muted-foreground">
                      <tr>
                        <th className="py-2 pr-3 font-medium">类型</th>
                        <th className="py-2 pr-3 font-medium">金额</th>
                        <th className="py-2 pr-3 font-medium">状态</th>
                        <th className="py-2 pr-3 font-medium">申请日期</th>
                        <th className="py-2 pr-3 font-medium">预计到账</th>
                        <th className="py-2 font-medium">打款日期</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(invite?.cash_requests || []).map((row) => (
                        <tr key={row.id} className="border-t border-border">
                          <td className="py-2 pr-3">{cashKind[row.kind || ''] || '奖励'}</td>
                          <td className="py-2 pr-3">{yuan(row.amount_fen)}</td>
                          <td className="py-2 pr-3">{cashStatus[row.status] || row.status}</td>
                          <td className="py-2 pr-3">{when(row.requested_at)}</td>
                          <td className="py-2 pr-3">{when(row.due_at)}</td>
                          <td className="py-2">{when(row.paid_at)}</td>
                        </tr>
                      ))}
                      {invite && invite.cash_requests.length === 0 && <tr><td className="py-3 text-muted-foreground" colSpan={6}>还没有兑现申请。</td></tr>}
                    </tbody>
                  </table>
                </div>
                {invite && invite.coupons.length > 0 && <p className="mt-3 text-sm">优惠券：{invite.coupons.map((coupon) => `${coupon.label} ${Math.round(Number(coupon.rate) * 100)}%（${coupon.status}）`).join('、')}</p>}
                <div className="mt-4 flex flex-wrap gap-2">
                  <button type="button" className="h-10 rounded-lg border border-border px-3 text-sm" onClick={() => void copyLink()}>复制链接</button>
                  <button type="button" className="h-10 rounded-lg bg-primary px-3 text-sm text-primary-foreground disabled:opacity-50" disabled={!invite || invite.discount_fen <= 0} onClick={() => void claimCash()}>申请兑现</button>
                  <button type="button" className="h-10 rounded-lg border border-border px-3 text-sm disabled:opacity-50" disabled={!invite || invite.draw_chances <= 0} onClick={() => void drawOnce()}>抽现金</button>
                </div>
                {(inviteError || notice) && <p className="mt-3 text-sm text-muted-foreground">{inviteError || notice}</p>}
              </>
            )}
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}
