export const TRADE_ROUTES = {
  domestic: { origin_country: 'CN', target_market: 'CN', tax_regime: 'domestic', route: 'CN-CN', market_pack: 'domestic', label: '国内' },
  cn_us: { origin_country: 'CN', target_market: 'US', tax_regime: 'cn_us', route: 'CN-US', market_pack: 'cn_us', label: '中国 → 美国' },
  cn_hk: { origin_country: 'CN', target_market: 'HK', tax_regime: 'cn_hk', route: 'CN-HK', market_pack: 'cn_hk', label: '中国 → 香港' },
  cn_au: { origin_country: 'CN', target_market: 'AU', tax_regime: 'cn_au', route: 'CN-AU', market_pack: 'cn_au', label: '中国 → 澳大利亚' },
  us_cn: { origin_country: 'US', target_market: 'CN', tax_regime: 'domestic', route: 'US-CN', market_pack: 'us_cn', label: '美国 → 中国' },
} as const

export type RouteId = keyof typeof TRADE_ROUTES

export const DEFAULT_ROUTE: RouteId = 'cn_us'
const KEY = 'pickglobal.trade-route'

export function isRouteId(value: string | null | undefined): value is RouteId {
  return Boolean(value && value in TRADE_ROUTES)
}

export function readTradeRoute(): RouteId {
  if (typeof window === 'undefined') return DEFAULT_ROUTE
  const saved = window.localStorage.getItem(KEY)
  return isRouteId(saved) ? saved : DEFAULT_ROUTE
}

export function writeTradeRoute(id: RouteId) {
  window.localStorage.setItem(KEY, id)
  window.dispatchEvent(new Event('pickglobal-route'))
}
