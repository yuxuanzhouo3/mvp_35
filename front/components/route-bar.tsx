'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { DEFAULT_ROUTE, TRADE_ROUTES, isRouteId, readTradeRoute, writeTradeRoute, type RouteId } from '@/lib/trade-route'

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

  return (
    <div className="shrink-0">
      <p className="text-xs font-semibold tracking-wide text-primary">路线</p>
      <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
        {(Object.keys(TRADE_ROUTES) as RouteId[]).map((id) => {
          const active = route === id
          return (
            <button
              key={id}
              type="button"
              className={`h-12 shrink-0 rounded-2xl px-5 text-base font-semibold ${active ? 'bg-primary text-primary-foreground shadow-md' : 'border border-border bg-card text-foreground'}`}
              aria-pressed={active}
              onClick={() => choose(id)}
            >
              {TRADE_ROUTES[id].label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
