'use client'

import { FormEvent, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Globe2 } from 'lucide-react'
import { adminLogin } from '@/lib/admin-session'
import { primaryButton } from '../components'
import { GuideVideo } from '@/components/guide-video'

export default function AdminLoginPage() {
  const router = useRouter()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setError('')
    try {
      await adminLogin(username.trim(), password)
      router.replace('/admin')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '登录失败')
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="relative grid min-h-screen place-items-center bg-[#10203f] px-4">
      <div className="absolute right-4 top-4"><GuideVideo onDark /></div>
      <form onSubmit={onSubmit} className="w-full max-w-md rounded-3xl bg-white p-8 shadow-2xl">
        <div className="mb-6 flex items-center gap-3">
          <div className="grid size-11 place-items-center rounded-xl bg-blue-500 text-white"><Globe2 className="size-5" /></div>
          <div>
            <div className="text-lg font-bold text-slate-950">PickGlobal</div>
            <div className="text-xs uppercase tracking-[.16em] text-slate-400">Platform Admin</div>
          </div>
        </div>
        <h1 className="text-2xl font-bold text-slate-950">登录管理后台</h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">初始账号 admin / admin。登录后可在平台设置里修改密码。</p>
        <label className="mt-6 block text-sm font-medium text-slate-700">
          用户名
          <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" className="admin-focus mt-1.5 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm" />
        </label>
        <label className="mt-4 block text-sm font-medium text-slate-700">
          密码
          <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" className="admin-focus mt-1.5 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm" />
        </label>
        {error && <p className="mt-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <button className={`${primaryButton} mt-6 w-full`} disabled={pending} type="submit">{pending ? '正在登录' : '登录'}</button>
      </form>
    </div>
  )
}
