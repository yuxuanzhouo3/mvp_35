export function PayBrandMark({ method, className = 'size-5' }: { method: 'wechat' | 'alipay'; className?: string }) {
  if (method === 'wechat') {
    return (
      <svg viewBox="0 0 32 32" className={className} aria-hidden>
        <circle cx="16" cy="16" r="16" fill="#07C160" />
        <path
          fill="#fff"
          d="M12.2 10.4c-3.6 0-6.5 2.5-6.5 5.6 0 1.8 1.1 3.4 2.8 4.4l-.6 2 2.3-1.2c.7.2 1.4.3 2 .3.2 0 .5 0 .7-.1-.2-.5-.3-1.1-.3-1.7 0-3.2 3.1-5.8 6.9-5.8.2 0 .4 0 .6 0-1-2.1-3.6-3.5-7.9-3.5zm-2.5 3.2a1 1 0 1 1 0-2 1 1 0 0 1 0 2zm5.1 0a1 1 0 1 1 0-2 1 1 0 0 1 0 2z"
        />
        <path
          fill="#fff"
          d="M23.6 15.6c-3.2 0-5.8 2.2-5.8 4.9 0 1.6 1 3 2.5 3.9l-.5 1.7 2.1-1.1c.6.2 1.2.3 1.7.3 3.2 0 5.8-2.2 5.8-4.8s-2.6-4.9-5.8-4.9zm-2.1 3.6a.85.85 0 1 1 0-1.7.85.85 0 0 1 0 1.7zm4.2 0a.85.85 0 1 1 0-1.7.85.85 0 0 1 0 1.7z"
        />
      </svg>
    )
  }
  // Path mark (no system font) so mobile WebViews do not show a blank/garbled glyph.
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill="#1677FF" />
      <path
        fill="#fff"
        d="M9.2 8.6h3.4c2.7 0 4.4 1.4 4.4 3.7 0 2.5-1.9 4-4.8 4H12.1v6.1H9.2V8.6zm3.1 5.7h1c1.2 0 1.9-.6 1.9-1.7s-.6-1.6-1.8-1.6h-1.1v3.3z"
      />
      <path
        fill="#fff"
        d="M18.2 12.4c0-2.2 1.6-3.8 4-3.8 1.1 0 2 .3 2.6.7l-.9 2.1c-.5-.3-1-.5-1.6-.5-1.1 0-1.8.7-1.8 1.8v.1c0 1.1.7 1.8 1.9 1.8.6 0 1.2-.2 1.7-.5l.9 2c-.7.5-1.6.7-2.7.7-2.5 0-4.1-1.5-4.1-4.1v-.3z"
      />
      <path fill="#fff" d="M8.4 24.2h15.2v2H8.4z" />
    </svg>
  )
}
