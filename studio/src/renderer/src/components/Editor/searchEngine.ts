// Pure search helpers shared by the MarkdownEditor find/replace handle.
// No React, no editor view — just turns a query + document state into match ranges.
import type { EditorState } from '@codemirror/state'
import { SearchQuery } from '@codemirror/search'

export interface FindOptions {
  query: string
  caseSensitive: boolean
  wholeWord: boolean
  regexp: boolean
}

export interface MatchRange {
  from: number
  to: number
}

export interface MatchInfo {
  /** Total number of matches in the document. */
  total: number
  /** 1-based index of the active match, or 0 when nothing is selected. */
  current: number
}

const MAX_MATCHES = 50_000

/** Collect every match for `opts` across the whole document, in document order. */
export function collectMatches(state: EditorState, opts: FindOptions): MatchRange[] {
  if (!opts.query) return []
  let query: SearchQuery
  try {
    query = new SearchQuery({
      search: opts.query,
      caseSensitive: opts.caseSensitive,
      wholeWord: opts.wholeWord,
      regexp: opts.regexp,
    })
  } catch {
    return []
  }
  if (!query.valid) return []

  const matches: MatchRange[] = []
  const cursor = query.getCursor(state)
  for (let next = cursor.next(); !next.done; next = cursor.next()) {
    if (next.value.from === next.value.to) continue
    matches.push({ from: next.value.from, to: next.value.to })
    if (matches.length >= MAX_MATCHES) break
  }
  return matches
}
