/**
 * Client adapter, following the detection used in mvp_1 and mvp_24:
 * user agent first, then shell globals (WeChat mini program, Android WebView,
 * WKWebView, Electron, Tauri). The page layout follows the surface; native
 * packages are still this web shell until a store build is published.
 */

export type ClientSurface = 'phone' | 'ipad' | 'miniprogram' | 'desktop' | 'web'
export type ClientOs = 'ios' | 'android' | 'windows' | 'macos' | 'linux' | 'unknown'
export type ClientShell =
  | 'browser'
  | 'wechat'
  | 'miniprogram'
  | 'android-webview'
  | 'ios-webview'
  | 'electron'
  | 'tauri'

export type ClientLabel = '手机' | 'iPad' | '微信小程序' | 'Web' | 'Mac' | 'Windows' | 'Linux'

export interface ClientInfo {
  surface: ClientSurface
  os: ClientOs
  shell: ClientShell
  label: ClientLabel
}

export interface ClientSignals {
  userAgent: string
  maxTouchPoints?: number
  wxEnvironment?: string | null
  search?: string
  electron?: boolean
  tauri?: boolean
  androidBridge?: boolean
  webkitHandlers?: boolean
}

export function detectClient(signals: ClientSignals): ClientInfo {
  const ua = signals.userAgent || ''
  const lower = ua.toLowerCase()
  const miniprogram =
    lower.includes('miniprogram') ||
    signals.wxEnvironment === 'miniprogram' ||
    (signals.search || '').includes('_wxjs_environment=miniprogram')

  const ipad = /ipad/i.test(ua) || (/macintosh/i.test(ua) && (signals.maxTouchPoints ?? 0) > 1 && !/iphone/i.test(ua))
  const iphone = /iphone|ipod/i.test(ua)
  const android = /android/i.test(ua)
  const androidPhone = android && /mobile/i.test(ua)
  const androidTablet = android && !androidPhone

  let os: ClientOs = 'unknown'
  if (iphone || ipad) os = 'ios'
  else if (android) os = 'android'
  else if (/windows/i.test(ua)) os = 'windows'
  else if (/mac os x|macintosh/i.test(ua)) os = 'macos'
  else if (/linux/i.test(ua) || /cros/i.test(ua)) os = 'linux'

  let shell: ClientShell = 'browser'
  if (miniprogram) shell = 'miniprogram'
  else if (signals.tauri) shell = 'tauri'
  else if (signals.electron || lower.includes('electron')) shell = 'electron'
  else if (android && (lower.includes('; wv') || lower.includes(' wv') || signals.androidBridge)) shell = 'android-webview'
  else if ((iphone || ipad) && (signals.webkitHandlers || (!/safari/i.test(lower) && /applewebkit/i.test(lower)))) shell = 'ios-webview'
  else if (lower.includes('micromessenger')) shell = 'wechat'

  if (miniprogram) return { surface: 'miniprogram', os, shell, label: '微信小程序' }
  if (ipad || androidTablet) return { surface: 'ipad', os, shell, label: 'iPad' }
  if (iphone || androidPhone) return { surface: 'phone', os, shell, label: '手机' }
  if (os === 'windows') return { surface: 'desktop', os, shell, label: 'Windows' }
  if (os === 'macos') return { surface: 'desktop', os, shell, label: 'Mac' }
  if (os === 'linux') return { surface: 'desktop', os, shell, label: 'Linux' }
  return { surface: 'web', os, shell, label: 'Web' }
}

export type FingerScaleMode = 'off' | 'native' | 'gesture'

export function fingerScaleMode(
  info: ClientInfo | null,
  extra: { userAgent?: string; shortSide?: number; touchPoints?: number } = {},
): { mode: FingerScaleMode; watch: boolean } {
  const ua = extra.userAgent || ''
  const watch =
    /\bwatch\b|watchos|wear ?os/i.test(ua) ||
    ((extra.shortSide ?? 1000) > 0 && (extra.shortSide ?? 1000) <= 280 && (extra.touchPoints ?? 0) > 0)
  const touchDevice = watch || info?.surface === 'phone' || info?.surface === 'ipad' || info?.surface === 'miniprogram'
  if (!touchDevice) return { mode: 'off', watch: false }
  const shellBlocksPinch =
    watch ||
    info?.shell === 'wechat' ||
    info?.shell === 'miniprogram' ||
    info?.shell === 'android-webview' ||
    info?.shell === 'ios-webview'
  return { mode: shellBlocksPinch ? 'gesture' : 'native', watch }
}

export function readClient(): ClientInfo | null {
  if (typeof window === 'undefined') return null
  const host = window as Window & {
    __TAURI__?: unknown
    Android?: unknown
    AndroidInterface?: unknown
    __wxjs_environment?: string
    webkit?: { messageHandlers?: unknown }
  }
  return detectClient({
    userAgent: navigator.userAgent,
    maxTouchPoints: navigator.maxTouchPoints,
    wxEnvironment: host.__wxjs_environment ?? null,
    search: window.location.search,
    tauri: typeof host.__TAURI__ !== 'undefined',
    androidBridge: typeof host.Android !== 'undefined' || typeof host.AndroidInterface !== 'undefined',
    webkitHandlers: typeof host.webkit?.messageHandlers !== 'undefined',
  })
}
