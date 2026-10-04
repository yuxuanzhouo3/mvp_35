'use client'

import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Link from 'next/link'
import { ChevronDown, CreditCard, Gift, LogOut, Settings, User } from 'lucide-react'
import { api } from '@/lib/api'

type Profile = {
  user: { id?: string; display_name?: string; username?: string; email?: string; phone?: string; role?: string }
  tenant: { plan_id?: string; name?: string }
  role?: string
}

type Person = { id: string; name: string; email_masked?: string | null }
type InviteEvent = {
  invitee_name: string
  link: string
  invited_at?: string | null
  paid_at?: string | null
  paid_fen: number
  reward_fen: number
}
type CashRequest = { id: string; kind?: string; amount_fen: number; status: string; due_at?: string | null }
type Coupon = { id: string; label: string; rate: string; status: string }
type Invite = {
  invite_code: string
  share_path: string
  used_by: Person[]
  invited_later: Person[]
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

export function UserMenu({ name, onLogout }: { name: string; onLogout: () => void }) {
  const [open, setOpen] = useState(false)
  const [dialog, setDialog] = useState<'settings' | 'invite' | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [invite, setInvite] = useState<Invite | null>(null)
  const [notice, setNotice] = useState('')
  const [density, setDensity] = useState('comfortable')
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const saved = window.localStorage.getItem('pickglobal.density') || 'comfortable'
    setDensity(saved)
    document.documentElement.dataset.density = saved
  }, [])

  useEffect(() => {
    function close(event: MouseEvent) {
      if (!box.current?.contains(event.target as Node)) setOpen(false)
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
      api<Invite>('/users/me/invite').then(setInvite).catch(() => undefined)
    }
  }

  function saveDensity(next: string) {
    setDensity(next)
    window.localStorage.setItem('pickglobal.density', next)
    document.documentElement.dataset.density = next
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
  const userId = profile?.user.id || ''
  const item = 'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-muted'

  return (
    <div className="relative" ref={box}>
      <button
        type="button"
        className="inline-flex h-9 max-w-[11rem] items-center gap-1.5 rounded-lg border border-border bg-background px-2.5 text-sm text-foreground hover:bg-muted"
        onClick={toggleMenu}
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <User className="size-4 shrink-0 text-muted-foreground" />
        <span className="truncate">{displayName}</span>
        <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-72 rounded-xl border border-border bg-card p-1.5 text-sm shadow-lg" role="menu">
          <div className="rounded-lg px-3 py-2.5">
            <p className="text-xs text-muted-foreground">个人信息</p>
            <p className="mt-1 truncate font-medium">{displayName}</p>
            {contact && <p className="truncate text-xs text-muted-foreground">{contact}</p>}
            {userId && <p className="mt-1 truncate text-xs text-muted-foreground">用户 ID {userId}</p>}
            <p className="mt-2 inline-flex rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">Premium Pro · {plan}</p>
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
        </div>
      )}
      {dialog && createPortal(
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/45 p-4" onClick={() => setDialog(null)}>
          <div className="max-h-[86vh] w-full max-w-md overflow-y-auto rounded-2xl border border-border bg-card p-5 shadow-2xl" onClick={(event) => event.stopPropagation()} role="dialog">
            {dialog === 'settings' && (
              <>
                <h2 className="text-lg font-semibold">界面设置</h2>
                <p className="mt-1 text-sm text-muted-foreground">{displayName}{contact ? ` · ${contact}` : ''}</p>
                <div className="mt-4 flex gap-2">
                  <button type="button" className={`h-10 flex-1 rounded-lg text-sm ${density === 'comfortable' ? 'bg-primary text-primary-foreground' : 'border border-border'}`} onClick={() => saveDensity('comfortable')}>舒适</button>
                  <button type="button" className={`h-10 flex-1 rounded-lg text-sm ${density === 'compact' ? 'bg-primary text-primary-foreground' : 'border border-border'}`} onClick={() => saveDensity('compact')}>紧凑</button>
                </div>
              </>
            )}
            {dialog === 'invite' && (
              <>
                <h2 className="text-lg font-semibold">邀请</h2>
                <p className="mt-1 text-sm text-muted-foreground">好友用这条链接注册。付费后奖励按 10% 先留在账户里当优惠。</p>
                <div className="mt-4 rounded-xl border border-border bg-muted/40 p-3">
                  <p className="text-xs text-muted-foreground">邀请码</p>
                  <p className="mt-1 font-mono text-base">{invite?.invite_code || '正在生成…'}</p>
                  <p className="mt-3 break-all font-mono text-xs text-muted-foreground">{invite ? invite.share_path : ''}</p>
                </div>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">已邀请 {invite?.used_by.length ?? 0} 人，当前优惠 {yuan(invite?.discount_fen ?? 0)}。申请兑现后，现金在 5 个工作日内打出。</p>
                <p className="mt-1 text-sm text-muted-foreground">连续登录 {invite?.login_streak ?? 0} 天。满 7 天 1 次抽奖，满 14 天再加 2 次，满 30 天奖励现金。可抽 {invite?.draw_chances ?? 0} 次。</p>
                {invite && invite.coupons.length > 0 && <p className="mt-2 text-sm">优惠券：{invite.coupons.map((coupon) => `${coupon.label} ${Math.round(Number(coupon.rate) * 100)}%`).join('、')}</p>}
                {invite && invite.events.length > 0 && (
                  <ul className="mt-3 max-h-32 space-y-1 overflow-y-auto text-xs leading-5 text-muted-foreground">
                    {invite.events.map((event) => (
                      <li key={`${event.invitee_name}-${event.paid_at || event.invited_at}`}>
                        {event.invited_at?.slice(0, 10) || '—'} 邀请 {event.invitee_name || '用户'}
                        {event.paid_fen > 0 ? `，付费 ${yuan(event.paid_fen)}，奖励 ${yuan(event.reward_fen)}` : '，尚未付费'}
                      </li>
                    ))}
                  </ul>
                )}
                {invite && invite.cash_requests.length > 0 && (
                  <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
                    {invite.cash_requests.map((row) => (
                      <li key={row.id}>{yuan(row.amount_fen)} · {row.status === 'paid' ? '已打款' : `待打款，${row.due_at?.slice(0, 10) || ''} 前`}</li>
                    ))}
                  </ul>
                )}
                <div className="mt-4 flex flex-wrap gap-2">
                  <button type="button" className="h-10 rounded-lg border border-border px-3 text-sm" onClick={() => void copyLink()}>复制链接</button>
                  <button type="button" className="h-10 rounded-lg bg-primary px-3 text-sm text-primary-foreground disabled:opacity-50" disabled={!invite || invite.discount_fen <= 0} onClick={() => void claimCash()}>申请兑现</button>
                  <button type="button" className="h-10 rounded-lg border border-border px-3 text-sm disabled:opacity-50" disabled={!invite || invite.draw_chances <= 0} onClick={() => void drawOnce()}>抽现金</button>
                </div>
                {notice && <p className="mt-3 text-sm text-muted-foreground">{notice}</p>}
              </>
            )}
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}
