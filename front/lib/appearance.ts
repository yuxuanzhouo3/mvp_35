export type ThemeChoice = 'light' | 'dark' | 'system'
export type FontChoice = 'default' | 'serif' | 'mono'
export type FontSizeChoice = '14' | '16' | '18'
export type DensityChoice = 'comfortable' | 'compact'

export type Appearance = {
  theme: ThemeChoice
  font: FontChoice
  fontSize: FontSizeChoice
  density: DensityChoice
  ads: boolean
}

export const APPEARANCE_KEY = 'pickglobal.appearance'

export const defaultAppearance: Appearance = {
  theme: 'light',
  font: 'default',
  fontSize: '16',
  density: 'comfortable',
  ads: true,
}

export const APPEARANCE_BOOT = `(function(){try{var s=JSON.parse(localStorage.getItem('pickglobal.appearance')||'{}');var d=localStorage.getItem('pickglobal.density');var theme=s.theme==='dark'||s.theme==='system'?s.theme:'light';var dark=theme==='dark'||(theme==='system'&&matchMedia('(prefers-color-scheme: dark)').matches);var root=document.documentElement;root.classList.toggle('dark',!!dark);root.dataset.font=s.font==='serif'||s.font==='mono'?s.font:'default';root.dataset.density=s.density==='compact'||d==='compact'?'compact':'comfortable';root.style.setProperty('--pg-font',(s.fontSize==='14'||s.fontSize==='18'?s.fontSize:'16')+'px');root.dataset.ads=s.ads===false?'off':'on';}catch(e){}})();`

export function readAppearance(): Appearance {
  if (typeof window === 'undefined') return defaultAppearance
  try {
    const parsed = JSON.parse(window.localStorage.getItem(APPEARANCE_KEY) || '{}') as Partial<Appearance>
    const legacy = window.localStorage.getItem('pickglobal.density')
    return {
      theme: parsed.theme === 'dark' || parsed.theme === 'system' ? parsed.theme : 'light',
      font: parsed.font === 'serif' || parsed.font === 'mono' ? parsed.font : 'default',
      fontSize: parsed.fontSize === '14' || parsed.fontSize === '18' ? parsed.fontSize : '16',
      density: parsed.density === 'compact' || legacy === 'compact' ? 'compact' : 'comfortable',
      ads: parsed.ads !== false,
    }
  } catch {
    return defaultAppearance
  }
}

export function applyAppearance(next: Appearance) {
  const root = document.documentElement
  const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  root.classList.toggle('dark', next.theme === 'dark' || (next.theme === 'system' && systemDark))
  root.dataset.font = next.font
  root.dataset.density = next.density
  root.style.setProperty('--pg-font', `${next.fontSize}px`)
  root.dataset.ads = next.ads ? 'on' : 'off'
}

export function writeAppearance(next: Appearance) {
  window.localStorage.setItem(APPEARANCE_KEY, JSON.stringify(next))
  window.localStorage.setItem('pickglobal.density', next.density)
  applyAppearance(next)
  window.dispatchEvent(new Event('pickglobal-appearance'))
}
