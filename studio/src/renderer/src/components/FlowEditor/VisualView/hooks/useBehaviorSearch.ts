import { useEffect, useRef, useState } from 'react'
import type { BehaviorItem } from './useBehaviorList'

interface UseBehaviorSearchResult {
  query: string
  setQuery: (q: string) => void
  activeIndex: number
  filtered: BehaviorItem[]
  searchRef: React.RefObject<HTMLInputElement>
  listRef: React.RefObject<HTMLUListElement>
  handleSearchKeyDown: (e: React.KeyboardEvent) => void
}

export function useBehaviorSearch(
  behaviors: BehaviorItem[],
  onSelect: (name: string) => void,
): UseBehaviorSearchResult {
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const searchRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)

  const filtered = behaviors.filter((b) => b.name.toLowerCase().includes(query.toLowerCase()))

  useEffect(() => { setActiveIndex(0) }, [query])

  useEffect(() => {
    const list = listRef.current
    if (!list) return
    const item = list.children[activeIndex] as HTMLElement | undefined
    item?.scrollIntoView({ block: 'nearest' })
  }, [activeIndex])

  function handleSearchKeyDown(e: React.KeyboardEvent): void {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && filtered[activeIndex]) {
      e.preventDefault()
      onSelect(filtered[activeIndex].name)
    }
  }

  return { query, setQuery, activeIndex, filtered, searchRef, listRef, handleSearchKeyDown }
}
