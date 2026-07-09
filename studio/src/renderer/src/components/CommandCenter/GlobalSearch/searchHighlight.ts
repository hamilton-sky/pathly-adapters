// Pure helpers for the global-search dropdown. The backend search is HYBRID
// (BM25 keyword + semantic embedding), so a result may match by literal keyword or
// by meaning alone. These utilities let the UI (a) highlight literal token matches
// and (b) classify each hit as keyword (something is highlighted) vs semantic
// (matched by meaning only) so the two can be grouped separately.
import type { GlobalSearchHit } from '../../../store/commsStore'

export interface Segment {
  text: string
  hit: boolean
}

const escapeRe = (t: string): string => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

// Query → distinct lowercased tokens (≥2 chars, surrounding punctuation trimmed).
// Sub-2-char tokens are dropped so a stray "a"/"i" doesn't highlight half the text.
export function queryTokens(query: string): string[] {
  const seen = new Set<string>()
  for (const raw of query.toLowerCase().split(/\s+/)) {
    const t = raw.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '')
    if (t.length >= 2) seen.add(t)
  }
  return [...seen]
}

// Split text into ordered segments, flagging literal (case-insensitive) token matches
// so the caller can wrap the `hit` segments in <mark>. Longer tokens are matched first
// so "client" wins over a nested "cli".
export function splitSegments(text: string, tokens: string[]): Segment[] {
  if (!text || tokens.length === 0) return [{ text, hit: false }]
  const ordered = [...tokens].sort((a, b) => b.length - a.length)
  const re = new RegExp(`(${ordered.map(escapeRe).join('|')})`, 'gi')
  const lower = new Set(tokens)
  return text
    .split(re)
    .filter((p) => p !== '')
    .map((p) => ({ text: p, hit: lower.has(p.toLowerCase()) }))
}

// True when a literal query token appears anywhere the row renders it (board label,
// message text, or matched chunk) — i.e. the row shows at least one highlight.
// Everything else matched by meaning only, and is a semantic hit.
export function isKeywordHit(hit: GlobalSearchHit, tokens: string[]): boolean {
  if (tokens.length === 0) return true
  const hay = `${hit.boardLabel}\n${hit.message.text}\n${hit.message.matchedChunk ?? ''}`.toLowerCase()
  return tokens.some((t) => hay.includes(t))
}
