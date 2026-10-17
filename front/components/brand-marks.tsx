import {
  Brain,
  Clapperboard,
  Globe2,
  Handshake,
  MapPinned,
  Percent,
  Share2,
  ShoppingBag,
  Store,
} from 'lucide-react'

const channelIcon = {
  ecommerce: ShoppingBag,
  social: Share2,
  expo: Store,
  agency: Handshake,
  enrichment: Brain,
  geo_seo: MapPinned,
  content_dh: Clapperboard,
  cross_border: Globe2,
  raas: Percent,
} as const

export function ChannelMark({ id, className = 'size-8' }: { id: string; className?: string }) {
  const Icon = channelIcon[id as keyof typeof channelIcon] || Store
  return (
    <span className={`inline-flex items-center justify-center rounded-2xl bg-white/70 text-current shadow-sm ring-1 ring-black/5 ${className}`}>
      <Icon className="size-[55%]" strokeWidth={2.1} aria-hidden />
    </span>
  )
}

/** Compact platform badge used on B1–B5 login cards. */
export function PlatformMark({ platform, className = 'size-7' }: { platform: string; className?: string }) {
  const mark = platformMarks[platform] || { bg: '#64748b', label: platform.slice(0, 1).toUpperCase() }
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-lg text-[11px] font-bold text-white ${className}`}
      style={{ background: mark.bg }}
      aria-hidden
    >
      {mark.label}
    </span>
  )
}

const platformMarks: Record<string, { bg: string; label: string }> = {
  amazon: { bg: '#FF9900', label: 'A' },
  temu: { bg: '#FF6A00', label: 'T' },
  walmart: { bg: '#0071DC', label: 'W' },
  taobao: { bg: '#FF5000', label: '淘' },
  pinduoduo: { bg: '#E02E24', label: '拼' },
  linkedin: { bg: '#0A66C2', label: 'in' },
  facebook: { bg: '#1877F2', label: 'f' },
  wechat_mini: { bg: '#07C160', label: '微' },
  douyin: { bg: '#111827', label: '抖' },
  xiaohongshu: { bg: '#FF2442', label: '红' },
  kuaishou: { bg: '#FF4906', label: '快' },
  alibaba_com: { bg: '#FF6A00', label: '国' },
  canton_fair: { bg: '#DC2626', label: '广' },
  global_sources: { bg: '#4F46E5', label: '环' },
  ciie: { bg: '#7C3AED', label: '进' },
  online_expo: { bg: '#C026D3', label: '展' },
  qichacha: { bg: '#0D9488', label: '企' },
  tianyancha: { bg: '#0891B2', label: '天' },
  qixin: { bg: '#65A30D', label: '启' },
  agent_1: { bg: '#0F766E', label: '1' },
  agent_2: { bg: '#0E7490', label: '2' },
  agent_3: { bg: '#0369A1', label: '3' },
}
