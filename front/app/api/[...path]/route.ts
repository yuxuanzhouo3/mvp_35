import { NextRequest } from 'next/server'

export const dynamic = 'force-dynamic'

const drop = new Set(['host', 'connection', 'content-length', 'transfer-encoding'])

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params
  const target = (process.env.API_PROXY_TARGET || 'http://127.0.0.1:8000').replace(/\/$/, '')
  const incoming = new URL(request.url)
  const dest = `${target}/api/${path.join('/')}${incoming.search}`
  const headers = new Headers(request.headers)
  drop.forEach((name) => headers.delete(name))
  const init: RequestInit = { method: request.method, headers, redirect: 'manual' }
  if (request.method !== 'GET' && request.method !== 'HEAD') init.body = await request.arrayBuffer()
  const response = await fetch(dest, init)
  const out = new Headers(response.headers)
  out.delete('content-encoding')
  out.delete('content-length')
  return new Response(response.body, { status: response.status, headers: out })
}

export const GET = proxy
export const POST = proxy
export const PUT = proxy
export const PATCH = proxy
export const DELETE = proxy
