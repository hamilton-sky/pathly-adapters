import { useCallback, useEffect, useRef, useState } from 'react'
import { Search, X } from 'lucide-react'
import { useCommsStore, type GlobalSearchHit } from '../../../store/commsStore'
import { Tooltip } from '../../ui'
import s from './GlobalSearch.module.css'

interface Props {
  /** Navigate to the hit's board and flash the matched message. */
  onOpenResult: (hit: GlobalSearchHit) => void
}

// Collapsible cross-board search for the top bar. Collapsed = a search icon; click
// expands an input that, on Enter, fans out /comms/search across every board and lists
// the matches in a dropdown. Picking one jumps to its board and flashes the message.
export function GlobalSearch({ onOpenResult }: Props): JSX.Element {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const hits = useCommsStore((st) => st.globalHits)
  const searching = useCommsStore((st) => st.globalSearching)
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
  const pick = (hit: GlobalSearchHit): void => { onOpenResult(hit); close() }

  return (
    <div className={s.wrap} ref={wrapRef}>
      {open ? (
        <div className={s.field}>
          <Search size={13} className={s.fieldIco} />
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
      ) : (
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
      )}

      {open && (searching || hits) && (
        <div className={s.results} role="listbox">
          {searching && <div className={s.hint}>Searching every board…</div>}
          {!searching && hits && hits.length === 0 && (
            <div className={s.hint}>No matches across any board.</div>
          )}
          {!searching && hits && hits.map((h) => (
            <button
              type="button"
              role="option"
              aria-selected="false"
              key={`${h.boardKey}:${h.message.id}`}
              className={s.hit}
              onClick={() => pick(h)}
            >
              <span className={s.hitTop}>
                <span className={s.hitBoard}>{h.boardLabel}</span>
                <span className={s.hitType} data-type={h.message.type}>{h.message.type}</span>
              </span>
              <span className={s.hitText}>{h.message.text}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
