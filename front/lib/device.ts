/** Coarse pointer / narrow viewport — treat as phone for camera, pay, and voice fallbacks. */
export function isPhoneClient() {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(pointer: coarse), (max-width: 767px)').matches
}

export function openExternalPay(url: string) {
  if (!url) return
  if (isPhoneClient()) {
    window.location.assign(url)
    return
  }
  const opened = window.open(url, '_blank', 'noopener,noreferrer')
  if (!opened) window.location.assign(url)
}

/** Native WeChat QR (`weixin://wxpay/...`) or H5 pay URL — jump into WeChat when possible. */
export function openWechatPay(url: string) {
  if (!url) return
  if (url.startsWith('weixin://') || isPhoneClient()) {
    window.location.href = url
    return
  }
  openExternalPay(url)
}
