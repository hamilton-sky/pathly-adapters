import { useEffect, useRef } from 'react'
import { ChevronDown, ChevronUp, X } from 'lucide-react'
import type { FindMode } from '../useFindReplace'
import type { MatchInfo } from '../searchEngine'
import styles from './FindReplaceBar.module.css'

interface FindReplaceBarProps {
  mode: FindMode
  query: string
  replaceText: string
  info: MatchInfo
  onQueryChange: (v: string) => void
  onReplaceChange: (v: string) => void
  onNext: () => void
  onPrev: () => void
  onReplaceOne: () => void
  onReplaceAll: () => void
  onClose: () => void
}

export function FindReplaceBar(props: FindReplaceBarProps): JSX.Element {
  const { mode, query, replaceText, info, onQueryChange, onReplaceChange } = props
  const { onNext, onPrev, onReplaceOne, onReplaceAll, onClose } = props
  const findInputRef = useRef<HTMLInputElement>(null)
  const replaceInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const el = mode === 'replace' ? replaceInputRef.current : findInputRef.current
    el?.focus()
    el?.select()
  }, [mode])

  const hasMatches = info.total > 0
  const countLabel = hasMatches ? `${info.current} of ${info.total}` : 'No results'

  function onFindKeyDown(e: React.KeyboardEvent<HTMLInputElement>): void {
    if (e.key === 'Enter') {
      e.preventDefault()
      if (e.shiftKey) onPrev()
      else onNext()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    }
  }

  function onReplaceKeyDown(e: React.KeyboardEvent<HTMLInputElement>): void {
    if (e.key === 'Enter') {
      e.preventDefault()
      onReplaceOne()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    }
  }

  return (
    <div className={styles.bar} role="search" aria-label="Find and replace">
      <div className={styles.row}>
        <input
          ref={findInputRef}
          className={styles.input}
          type="text"
          placeholder="Find..."
          aria-label="Find"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={onFindKeyDown}
        />
        <span className={styles.count} data-empty={hasMatches ? undefined : 'true'}>{countLabel}</span>
        <button
          type="button"
          className={styles.iconBtn}
          aria-label="Next match"
          title="Next match (Enter)"
          disabled={!hasMatches}
          onClick={onNext}
        >
          <ChevronDown size={15} />
        </button>
        <button
          type="button"
          className={styles.iconBtn}
          aria-label="Previous match"
          title="Previous match (Shift+Enter)"
          disabled={!hasMatches}
          onClick={onPrev}
        >
          <ChevronUp size={15} />
        </button>
        <button
          type="button"
          className={styles.iconBtn}
          aria-label="Close find bar"
          title="Close (Esc)"
          onClick={onClose}
        >
          <X size={15} />
        </button>
      </div>

      <div className={styles.row}>
        <input
          ref={replaceInputRef}
          className={styles.input}
          type="text"
          placeholder="Replace with..."
          aria-label="Replace with"
          value={replaceText}
          onChange={(e) => onReplaceChange(e.target.value)}
          onKeyDown={onReplaceKeyDown}
        />
        <button
          type="button"
          className={styles.textBtn}
          aria-label="Replace current match"
          title="Replace (Enter)"
          disabled={!hasMatches}
          onClick={onReplaceOne}
        >
          Replace
        </button>
        <button
          type="button"
          className={styles.textBtn}
          aria-label="Replace all matches"
          title="Replace all"
          disabled={!hasMatches}
          onClick={onReplaceAll}
        >
          All
        </button>
      </div>
    </div>
  )
}
