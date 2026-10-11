/** Soft brand fills for payment, platform login, and Path B cards. */

export const payTint = {
  wechat: {
    idle: 'border-emerald-200 bg-emerald-50 text-emerald-950',
    active: 'border-emerald-500 bg-emerald-100 text-emerald-950 ring-1 ring-emerald-400/40',
  },
  alipay: {
    idle: 'border-sky-200 bg-sky-50 text-sky-950',
    active: 'border-sky-500 bg-sky-100 text-sky-950 ring-1 ring-sky-400/40',
  },
} as const

export const platformTint: Record<string, { card: string; button: string }> = {
  amazon: { card: 'border-amber-300 bg-amber-50', button: 'bg-amber-600 hover:bg-amber-700' },
  temu: { card: 'border-orange-300 bg-orange-50', button: 'bg-orange-600 hover:bg-orange-700' },
  walmart: { card: 'border-blue-300 bg-blue-50', button: 'bg-blue-600 hover:bg-blue-700' },
  taobao: { card: 'border-orange-400 bg-orange-50', button: 'bg-orange-500 hover:bg-orange-600' },
  pinduoduo: { card: 'border-rose-300 bg-rose-50', button: 'bg-rose-600 hover:bg-rose-700' },
  linkedin: { card: 'border-sky-400 bg-sky-50', button: 'bg-sky-700 hover:bg-sky-800' },
  facebook: { card: 'border-blue-400 bg-blue-50', button: 'bg-blue-600 hover:bg-blue-700' },
  wechat_mini: { card: 'border-emerald-300 bg-emerald-50', button: 'bg-emerald-600 hover:bg-emerald-700' },
  douyin: { card: 'border-slate-400 bg-slate-100', button: 'bg-slate-800 hover:bg-slate-900' },
  xiaohongshu: { card: 'border-rose-400 bg-rose-50', button: 'bg-rose-500 hover:bg-rose-600' },
  kuaishou: { card: 'border-orange-400 bg-orange-50', button: 'bg-orange-500 hover:bg-orange-600' },
  alibaba_com: { card: 'border-orange-300 bg-orange-50', button: 'bg-orange-600 hover:bg-orange-700' },
  canton_fair: { card: 'border-red-300 bg-red-50', button: 'bg-red-600 hover:bg-red-700' },
  global_sources: { card: 'border-indigo-300 bg-indigo-50', button: 'bg-indigo-600 hover:bg-indigo-700' },
  ciie: { card: 'border-violet-300 bg-violet-50', button: 'bg-violet-600 hover:bg-violet-700' },
  online_expo: { card: 'border-fuchsia-300 bg-fuchsia-50', button: 'bg-fuchsia-600 hover:bg-fuchsia-700' },
  qichacha: { card: 'border-teal-300 bg-teal-50', button: 'bg-teal-600 hover:bg-teal-700' },
  tianyancha: { card: 'border-cyan-300 bg-cyan-50', button: 'bg-cyan-600 hover:bg-cyan-700' },
  qixin: { card: 'border-lime-300 bg-lime-50', button: 'bg-lime-700 hover:bg-lime-800' },
  agent_1: { card: 'border-teal-300 bg-teal-50', button: 'bg-teal-600 hover:bg-teal-700' },
  agent_2: { card: 'border-cyan-300 bg-cyan-50', button: 'bg-cyan-600 hover:bg-cyan-700' },
  agent_3: { card: 'border-sky-300 bg-sky-50', button: 'bg-sky-600 hover:bg-sky-700' },
}

export const channelTint: Record<string, { card: string; code: string }> = {
  ecommerce: { card: 'border-orange-200 bg-orange-50/90 hover:border-orange-300', code: 'text-orange-700' },
  social: { card: 'border-sky-200 bg-sky-50/90 hover:border-sky-300', code: 'text-sky-700' },
  expo: { card: 'border-violet-200 bg-violet-50/90 hover:border-violet-300', code: 'text-violet-700' },
  agency: { card: 'border-teal-200 bg-teal-50/90 hover:border-teal-300', code: 'text-teal-700' },
  enrichment: { card: 'border-indigo-200 bg-indigo-50/90 hover:border-indigo-300', code: 'text-indigo-700' },
  geo_seo: { card: 'border-cyan-200 bg-cyan-50/90 hover:border-cyan-300', code: 'text-cyan-700' },
  content_dh: { card: 'border-rose-200 bg-rose-50/90 hover:border-rose-300', code: 'text-rose-700' },
  cross_border: { card: 'border-emerald-200 bg-emerald-50/90 hover:border-emerald-300', code: 'text-emerald-700' },
  raas: { card: 'border-amber-200 bg-amber-50/90 hover:border-amber-300', code: 'text-amber-700' },
}

export function tintForPlatform(platform: string) {
  return platformTint[platform] || { card: 'border-border bg-card', button: 'bg-primary hover:bg-primary/90' }
}

export function tintForChannel(id: string) {
  return channelTint[id] || { card: 'border-border bg-card', code: 'text-primary' }
}
