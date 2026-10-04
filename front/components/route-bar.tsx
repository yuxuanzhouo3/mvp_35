'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { DEFAULT_ROUTE, TRADE_ROUTES, isRouteId, placeName, readTradeRoute, writeTradeRoute, type RouteId } from '@/lib/trade-route'

export function RouteBar() {
  const [route, setRoute] = useState<RouteId>(DEFAULT_ROUTE)

  useEffect(() => {
    setRoute(readTradeRoute())
    api<{ user?: { trade_route?: string } }>('/users/me')
      .then((me) => {
        const saved = me.user?.trade_route
        if (!isRouteId(saved) || saved === readTradeRoute()) return
        writeTradeRoute(saved)
        setRoute(saved)
      })
      .catch(() => undefined)
    function sync() {
      setRoute(readTradeRoute())
    }
    window.addEventListener('pickglobal-route', sync)
    return () => window.removeEventListener('pickglobal-route', sync)
  }, [])

  function choose(id: RouteId) {
    writeTradeRoute(id)
    setRoute(id)
    void api('/tenants/current/trade-route', { method: 'PATCH', body: JSON.stringify({ route: id }) }).catch(() => undefined)
  }

  const spec = TRADE_ROUTES[route]
  return (
    <div className="flex shrink-0 items-center gap-2 overflow-x-auto overscroll-x-contain">
      {(Object.keys(TRADE_ROUTES) as RouteId[]).map((id) => {
        const active = route === id
        return (
          <button
            key={id}
            type="button"
            className={`h-9 shrink-0 rounded-full px-3 text-sm font-semibold ${active ? 'bg-blue-600 text-white' : 'border border-border bg-white text-slate-800 dark:bg-card dark:text-foreground'}`}
            aria-pressed={active}
            onClick={() => choose(id)}
          >
            {TRADE_ROUTES[id].label}
          </button>
        )
      })}
      <p className="ms-auto shrink-0 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-sm font-semibold text-slate-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-foreground" aria-label="起源地到目标地">
        {placeName(spec.origin_country)} → {placeName(spec.target_market)}
      </p>
    </div>
  )
}
