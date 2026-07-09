import { useCallback, useEffect, useRef, useState } from 'react'
import { Search, X } from 'lucide-react'
import { useCommsStore, type GlobalSearchHit } from '../../../store/commsStore'
import { Tooltip } from '../../ui'
import { SearchResults } from './SearchResults/SearchResults'
import s from './GlobalSearch.module.css'

interface Props {
  /** Navigate to the hit's board and flash the matched message. */
  onOpenResult: (hit: GlobalSearchHit) => void
}

// Collapsible cross-board search for the top bar. Collapsed = a search icon; click
// expands an input. Once open, pressing Enter OR clicking the magnifier fans out
// /comms/search across every board (hybrid keyword + semantic) and lists the matches
// below — split into keyword and semantic groups. Picking one jumps to its board.
export function GlobalSearch({ onOpenResult }: Props): JSX.Element {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const hits = useCommsStore((st) => st.globalHits)
  const searching = useCommsStore((st) => st.globalSearching)
  const query = useCommsStore((st) => st.globalQuery)
  const runGlobalSearch = useCommsStore((st) => st.runGlobalSearch)
  const clearGlobalSearch = useCommsStore((st) => st.clearGlobalSearch)
  const wrapRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const close = useCallback(() => {
    setOpen(false)
    setText('')
    clearGlobalSearch()
  }, [clearGlobalSearch])

  // Focus the field the moment it opens.
  useEffect(() => { if (open) inputRef.current?.focus() }, [open])

  // Click anywhere outside the search collapses it.
  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent): void => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) close()
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open, close])

  const submit = (): void => { if (text.trim()) void runGlobalSearch(text) }
  const pick = useCallback((hit: GlobalSearchHit): void => {
    onOpenResult(hit)
    close()
  }, [onOpenResult, close])

  if (!open) {
    return (
      <div className={s.wrap} ref={wrapRef}>
        <Tooltip label="Search all boards" description="Find a message across every board" placement="bottom">
          <button
            type="button"
            className={s.iconBtn}
            aria-label="Search all boards"
            aria-expanded="false"
            onClick={() => setOpen(true)}
          >
            <Search size={15} />
          </button>
        </Tooltip>
      </div>
    )
  }

  return (
    <div className={s.wrap} ref={wrapRef}>
      <div className={s.field}>
        <button
          type="button"
          className={s.fieldBtn}
          aria-label="Run search"
          onClick={() => { submit(); inputRef.current?.focus() }}
        >
          <Search size={13} />
        </button>
        <input
          ref={inputRef}
          className={s.input}
          placeholder="Search all boards…"
          value={text}
          onChange={(e) => setText(e.currentTarget.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') submit(); if (e.key === 'Escape') close() }}
        />
        <button type="button" className={s.clear} aria-label="Close search" onClick={close}>
          <X size={14} />
        </button>
      </div>

      <div className={s.results} role="listbox">
        <SearchResults query={query} hits={hits} searching={searching} onPick={pick} />
      </div>
    </div>
  )
}
