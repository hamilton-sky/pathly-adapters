import { useCallback, useEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'
import type { MarkdownEditorHandle } from './MarkdownEditor'
import type { MatchInfo } from './searchEngine'

export type FindMode = 'find' | 'replace'

const EMPTY_INFO: MatchInfo = { total: 0, current: 0 }

function searchOpts(query: string): { query: string; caseSensitive: boolean; wholeWord: boolean; regexp: boolean } {
  return { query, caseSensitive: false, wholeWord: false, regexp: false }
}

/**
 * Owns the find/replace bar state and drives the editor handle.
 * `enabled` gates the keyboard shortcuts (only the edit/split tabs mount the editor);
 * `resetKey` (the file path) clears the bar when the open document changes.
 */
export function useFindReplace(
  editorRef: RefObject<MarkdownEditorHandle>,
  enabled: boolean,
  resetKey: string | null,
) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<FindMode>('find')
  const [query, setQuery] = useState('')
  const [replaceText, setReplaceText] = useState('')
  const [info, setInfo] = useState<MatchInfo>(EMPTY_INFO)

  const queryRef = useRef('')
  const replaceRef = useRef('')
  const openRef = useRef(false)
  openRef.current = open

  const runSearch = useCallback((q: string): void => {
    const r = editorRef.current?.applySearch(searchOpts(q))
    setInfo(r ?? EMPTY_INFO)
  }, [editorRef])

  const onQueryChange = useCallback((q: string): void => {
    queryRef.current = q
    setQuery(q)
    runSearch(q)
  }, [runSearch])

  const onReplaceChange = useCallback((v: string): void => {
    replaceRef.current = v
    setReplaceText(v)
  }, [])

  const openBar = useCallback((m: FindMode): void => {
    setMode(m)
    setOpen(true)
    const selected = editorRef.current?.getSelectedText() ?? ''
    const seed = selected && !selected.includes('\n') ? selected : queryRef.current
    if (selected && !selected.includes('\n')) {
      queryRef.current = selected
      setQuery(selected)
    }
    runSearch(seed)
  }, [editorRef, runSearch])

  const close = useCallback((): void => {
    setOpen(false)
    editorRef.current?.clearSearch()
    editorRef.current?.focusEditor()
  }, [editorRef])

  const toggle = useCallback((m: FindMode): void => {
    if (openRef.current) close()
    else openBar(m)
  }, [close, openBar])

  const next = useCallback((): void => {
    const r = editorRef.current?.findNext()
    if (r) setInfo(r)
  }, [editorRef])

  const prev = useCallback((): void => {
    const r = editorRef.current?.findPrevious()
    if (r) setInfo(r)
  }, [editorRef])

  const replaceOne = useCallback((): void => {
    const r = editorRef.current?.replaceCurrent(replaceRef.current)
    if (r) setInfo(r)
  }, [editorRef])

  const replaceAll = useCallback((): void => {
    const r = editorRef.current?.replaceAll(replaceRef.current)
    if (r) setInfo(r)
  }, [editorRef])

  // Ctrl/Cmd+F → find, Ctrl/Cmd+H → replace, Escape → close.
  useEffect(() => {
    function onKey(e: KeyboardEvent): void {
      const mod = e.ctrlKey || e.metaKey
      if (mod && (e.key === 'f' || e.key === 'F')) {
        if (!enabled) return
        e.preventDefault()
        openBar('find')
      } else if (mod && (e.key === 'h' || e.key === 'H')) {
        if (!enabled) return
        e.preventDefault()
        openBar('replace')
      } else if (e.key === 'Escape' && openRef.current) {
        close()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [enabled, openBar, close])

  // Close (without stealing focus) when the editor unmounts via a tab switch.
  useEffect(() => {
    if (!enabled && open) setOpen(false)
  }, [enabled, open])

  // Reset everything when the open file changes.
  useEffect(() => {
    setOpen(false)
    setQuery('')
    setReplaceText('')
    setInfo(EMPTY_INFO)
    queryRef.current = ''
    replaceRef.current = ''
  }, [resetKey])

  return {
    open,
    mode,
    query,
    replaceText,
    info,
    setMode,
    onQueryChange,
    onReplaceChange,
    openBar,
    toggle,
    close,
    next,
    prev,
    replaceOne,
    replaceAll,
  }
}
