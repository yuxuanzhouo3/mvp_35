'use client'

import { FormEvent, useEffect, useState } from 'react'
import { adminApi } from '@/lib/admin-session'
import { Notice, PageHeader, Panel, primaryButton, selectClass } from '../components'

type Settings = { environment_label: string; timezone: string; window_days: number }

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>({ environment_label: 'TEST', timezone: 'Asia/Shanghai', window_days: 30 })
  const [currentPassword, setCurrentPassword] = useState('')
  const [nextPassword, setNextPassword] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    adminApi<Settings>('/admin/settings').then(setSettings).catch((reason: Error) => setError(reason.message))
  }, [])

  async function save(event: FormEvent) {
    event.preventDefault()
    setError('')
    try {
      const saved = await adminApi<Settings>('/admin/settings', { method: 'PATCH', body: JSON.stringify(settings) })
      setSettings(saved)
      setNotice('平台设置已保存')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '保存失败')
    }
  }

  async function changePassword(event: FormEvent) {
    event.preventDefault()
    setError('')
    try {
      await adminApi('/admin/settings/password', {
        method: 'POST',
        body: JSON.stringify({ current_password: currentPassword, new_password: nextPassword }),
      })
      setCurrentPassword('')
      setNextPassword('')
      setNotice('密码已更新，下次请用新密码登录')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '修改失败')
    }
  }

  return (
    <div className="mx-auto max-w-[820px]">
      <PageHeader eyebrow="Governance" title="平台设置" description="环境标识、统计时区和默认时间窗口。初始密码 admin 可以在这里改掉。" />
      <Notice message={notice} />
      <Notice message={error} tone="red" />
      <Panel title="运行配置">
        <form onSubmit={save} className="space-y-4 p-5">
          <label className="block text-sm font-medium text-slate-700">环境标识
            <select className={`${selectClass} mt-1.5 w-full`} value={settings.environment_label} onChange={(event) => setSettings({ ...settings, environment_label: event.target.value })}>
              <option value="TEST">TEST</option>
              <option value="PRODUCTION">PRODUCTION</option>
            </select>
          </label>
          <label className="block text-sm font-medium text-slate-700">时区
            <input value={settings.timezone} onChange={(event) => setSettings({ ...settings, timezone: event.target.value })} className="admin-focus mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm" />
          </label>
          <label className="block text-sm font-medium text-slate-700">默认窗口
            <select className={`${selectClass} mt-1.5 w-full`} value={settings.window_days} onChange={(event) => setSettings({ ...settings, window_days: Number(event.target.value) })}>
              <option value={7}>最近 7 天</option>
              <option value={30}>最近 30 天</option>
              <option value={90}>最近 90 天</option>
            </select>
          </label>
          <button className={primaryButton} type="submit">保存设置</button>
        </form>
      </Panel>
      <Panel title="修改登录密码" className="mt-5">
        <form onSubmit={changePassword} className="space-y-4 p-5">
          <input value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} type="password" required placeholder="当前密码" autoComplete="current-password" className="admin-focus w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm" />
          <input value={nextPassword} onChange={(event) => setNextPassword(event.target.value)} type="password" required minLength={4} placeholder="新密码，至少 4 位" autoComplete="new-password" className="admin-focus w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm" />
          <button className={primaryButton} type="submit">更新密码</button>
        </form>
      </Panel>
    </div>
  )
}
