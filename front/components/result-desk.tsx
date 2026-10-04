'use client'

import { useMemo, useState } from 'react'

type Filter<T> = {
  key: string
  label: string
  value: (item: T) => string
  labels?: Record<string, string>
}

type Sort<T> = {
  id: string
  label: string
  compare: (left: T, right: T) => number
}

export function ResultDesk<T>({
  items,
  placeholder,
  keywords,
  filters = [],
  sorts,
  pageSize = 5,
  empty,
  onSearch,
  render,
}: {
  items: T[]
  placeholder: string
  keywords: (item: T) => string
  filters?: Filter<T>[]
  sorts: Sort<T>[]
  pageSize?: number
  empty: string
  onSearch?: (query: string) => void
  render: (item: T) => React.ReactNode
}) {
  const [draft, setDraft] = useState('')
  const [query, setQuery] = useState('')
  const [openFilter, setOpenFilter] = useState(false)
  const [picked, setPicked] = useState<Record<string, string>>({})
  const [sortId, setSortId] = useState(sorts[0]?.id || '')
  const [page, setPage] = useState(0)
  const [limit, setLimit] = useState(pageSize)

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const sort = sorts.find((item) => item.id === sortId) || sorts[0]
    const next = items.filter((item) => {
      if (needle && !keywords(item).toLowerCase().includes(needle)) return false
      return filters.every((filter) => {
        const chosen = picked[filter.key]
        return !chosen || filter.value(item) === chosen
      })
    })
    if (sort) next.sort(sort.compare)
    return next
  }, [items, query, picked, sortId, filters, keywords, sorts])

  const size = Math.min(50, Math.max(1, Number.isFinite(limit) ? limit : pageSize))
  const pages = Math.max(1, Math.ceil(filtered.length / size))
  const current = Math.min(page, pages - 1)
  const slice = filtered.slice(current * size, current * size + size)

  function search() {
    setQuery(draft)
    setPage(0)
    onSearch?.(draft)
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          className="h-10 min-w-40 flex-1 rounded-xl border border-border bg-background px-3 text-sm"
          value={draft}
          placeholder={placeholder}
          aria-label={placeholder}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') search()
          }}
        />
        <button type="button" className="h-10 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground" onClick={search}>搜索</button>
        {filters.length > 0 && (
          <button type="button" className={`h-10 rounded-xl border px-4 text-sm ${openFilter ? 'border-primary text-primary' : 'border-border'}`} onClick={() => setOpenFilter((value) => !value)}>筛选</button>
        )}
        <label className="flex h-10 items-center gap-1 rounded-xl border border-border bg-background px-2 text-sm">
          最多
          <input
            className="w-12 bg-transparent text-center outline-none"
            type="number"
            min={1}
            max={50}
            aria-label="最多条数"
            value={limit}
            onChange={(event) => {
              const next = Number(event.target.value)
              setLimit(Number.isFinite(next) ? Math.min(50, Math.max(1, next)) : 1)
              setPage(0)
            }}
          />
        </label>
        <select
          className="h-10 rounded-xl border border-border bg-background px-3 text-sm"
          aria-label="排序"
          value={sortId}
          onChange={(event) => {
            setSortId(event.target.value)
            setPage(0)
          }}
        >
          {sorts.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
      </div>
      {openFilter && (
        <div className="flex flex-wrap gap-2">
          {filters.map((filter) => {
            const values = [...new Set(items.map((item) => filter.value(item)).filter(Boolean))]
            return (
              <select
                key={filter.key}
                className="h-10 rounded-xl border border-border bg-background px-3 text-sm"
                aria-label={filter.label}
                value={picked[filter.key] || ''}
                onChange={(event) => {
                  setPicked((current) => ({ ...current, [filter.key]: event.target.value }))
                  setPage(0)
                }}
              >
                <option value="">{filter.label}</option>
                {values.map((value) => <option key={value} value={value}>{filter.labels?.[value] || value}</option>)}
              </select>
            )
          })}
        </div>
      )}
      <div className="flex flex-col gap-2">
        {slice.map((item, index) => <div key={index}>{render(item)}</div>)}
        {filtered.length === 0 && <p className="text-sm text-muted-foreground">{empty}</p>}
      </div>
      <div className="flex items-center justify-between gap-3">
        <button type="button" className="h-10 rounded-xl border border-border px-4 text-sm disabled:opacity-40" disabled={current === 0} onClick={() => setPage(current - 1)}>上一页</button>
        <span className="text-sm text-muted-foreground">{current + 1} / {pages}</span>
        <button type="button" className="h-10 rounded-xl border border-border px-4 text-sm disabled:opacity-40" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>下一页</button>
      </div>
    </div>
  )
}
