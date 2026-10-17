'use client'

import { useEffect, useState, type KeyboardEvent } from 'react'

export const AI_PICK_PROMPTS = [
  '美国站 100 美元以内的二手 iPhone',
  '欧洲站家居收纳，成本 80 元以内',
  '澳洲站宠物用品，目标价 30 澳元',
  '香港站美妆护肤，优先看利润率',
  '国内站厨房小家电，走国内路线',
] as const

export const CHAT_PROMPTS = [
  '最近一份报告的利润和风险怎么样？',
  '这条路线的税费大概怎么算？',
  '为什么利润率低于 15%？',
  '专业版和免费版差在哪里？',
  '如何开始 B1 电商平台获客？',
] as const

export function PromptSuggest({
  options,
  value,
  onPick,
  active,
}: {
  options: readonly string[]
  value: string
  onPick: (text: string) => void
  active?: boolean
}) {
  const index = Math.max(0, options.findIndex((item) => item === value))
  const current = options.includes(value as typeof options[number]) ? index : -1

  return (
    <div className={`flex flex-wrap gap-1.5 ${active ? '' : 'opacity-90'}`} role="listbox" aria-label="默认输入选项">
      {options.map((item, i) => {
        const selected = current === i
        return (
          <button
            key={item}
            type="button"
            role="option"
            aria-selected={selected}
            className={`max-w-full truncate rounded-full border px-2.5 py-1 text-[11px] leading-4 transition sm:text-xs ${selected ? 'border-primary bg-primary/10 text-primary' : 'border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground'}`}
            onClick={() => onPick(item)}
          >
            {item}
          </button>
        )
      })}
    </div>
  )
}

/** Tab / arrows cycle default prompts when the field is focused. */
export function usePromptKeys(
  options: readonly string[],
  value: string,
  setValue: (next: string) => void,
) {
  const [cursor, setCursor] = useState(0)

  useEffect(() => {
    const at = options.findIndex((item) => item === value)
    if (at >= 0) setCursor(at)
  }, [options, value])

  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    const key = event.key
    if (key !== 'Tab' && key !== 'ArrowUp' && key !== 'ArrowDown' && key !== 'ArrowLeft' && key !== 'ArrowRight') return
    event.preventDefault()
    const delta = key === 'ArrowUp' || key === 'ArrowLeft' || (key === 'Tab' && event.shiftKey) ? -1 : 1
    const next = (cursor + delta + options.length) % options.length
    setCursor(next)
    setValue(options[next])
  }

  return { cursor, onKeyDown }
}
