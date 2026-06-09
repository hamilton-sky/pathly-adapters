/**
 * CSS Custom Highlight API helpers — no DOM mutation.
 * Works across inline elements (<code>, <strong>, etc.).
 * Requires Chrome 105+ / Electron 21+.
 */

import type { Comment, CommentColor } from '../useComments'

export const PENDING_HL = 'pathly-pending'
export const SUBMITTED_HL = 'pathly-submitted'
export const COMMENT_HL_PREFIX = 'pathly-comment-'
export const PULSE_HL = 'pathly-comment-pulse'

export const COMMENT_TINTS: Record<CommentColor, string> = {
  yellow: 'rgba(252, 211, 77, 0.24)',
  green:  'rgba(52, 211, 153, 0.22)',
  blue:   'rgba(96, 165, 250, 0.22)',
  purple: 'rgba(167, 139, 250, 0.22)',
  orange: 'rgba(249, 115, 22, 0.22)',
}

export const COMMENT_TINTS_PULSE: Record<CommentColor, string> = {
  yellow: 'rgba(252, 211, 77, 0.65)',
  green:  'rgba(52, 211, 153, 0.60)',
  blue:   'rgba(96, 165, 250, 0.60)',
  purple: 'rgba(167, 139, 250, 0.60)',
  orange: 'rgba(249, 115, 22, 0.60)',
}

const ALL_COMMENT_COLORS: CommentColor[] = ['yellow', 'green', 'blue', 'purple', 'orange']

const apiAvailable =
  typeof window !== 'undefined' && 'highlights' in CSS && 'Highlight' in window

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const HighlightCtor: (new (...r: Range[]) => unknown) | null = apiAvailable ? (window as any).Highlight : null

function setHL(name: string, ranges: Range[]): void {
  if (!apiAvailable || !HighlightCtor || !ranges.length) return
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(CSS as any).highlights.set(name, new HighlightCtor(...ranges))
}

function deleteHL(name: string): void {
  if (!apiAvailable) return
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(CSS as any).highlights.delete(name)
}

/** Find a Range for searchTerm inside container's text nodes — no DOM mutation. */
export function findTextRange(container: HTMLElement, searchTerm: string): Range | null {
  if (!searchTerm) return null
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null)
  while (walker.nextNode()) {
    const node = walker.currentNode as Text
    const nodeText = node.textContent ?? ''
    let start = nodeText.indexOf(searchTerm)
    let len = searchTerm.length

    if (start === -1) {
      // Whitespace-normalised fallback (browser adds \n at visual line wraps)
      const normNode = nodeText.replace(/\s+/g, ' ')
      const normIdx = normNode.indexOf(searchTerm)
      if (normIdx === -1) continue
      let s = 0, n = 0
      while (s < nodeText.length && n < normIdx) {
        if (/\s/.test(nodeText[s])) { while (s < nodeText.length && /\s/.test(nodeText[s])) s++; n++ }
        else { s++; n++ }
      }
      start = s
      while (s < nodeText.length && n < normIdx + searchTerm.length) {
        if (/\s/.test(nodeText[s])) { while (s < nodeText.length && /\s/.test(nodeText[s])) s++; n++ }
        else { s++; n++ }
      }
      len = s - start
    }

    const range = document.createRange()
    range.setStart(node, start)
    range.setEnd(node, start + len)
    return range
  }
  return null
}

/**
 * Find the best Range for an anchor string.
 * Uses progressive fallbacks to handle selections spanning inline <code> elements.
 */
export function findAnchorRange(container: HTMLElement, anchor: string): Range | null {
  const norm = anchor.replace(/\s+/g, ' ').trim()
  if (!norm) return null

  const found =
    findTextRange(container, norm) ??
    (norm.length > 60 ? findTextRange(container, norm.slice(0, 60)) : null) ??
    (norm.length > 30 ? findTextRange(container, norm.slice(0, 30)) : null)
  if (found) return found

  const words = norm.split(/\s+/)

  // › -separated chips (priority order lists with multiple adjacent <code> elements)
  const chips = norm.split(/\s*›\s*/)
  if (chips.length > 1) {
    for (const chip of chips) {
      const s = chip.trim()
      if (s.length >= 4) { const r = findTextRange(container, s); if (r) return r }
    }
  }
  // Selection starts inside a <code> element — strip leading words
  for (let skip = 1; skip < Math.min(words.length, 8); skip++) {
    const suffix = words.slice(skip).join(' ')
    if (suffix.length >= 8) { const r = findTextRange(container, suffix); if (r) return r }
  }
  // Selection ends inside a <code> element — strip trailing words
  for (let take = words.length - 1; take >= Math.max(1, words.length - 8); take--) {
    const prefix = words.slice(0, take).join(' ')
    if (prefix.length >= 8) { const r = findTextRange(container, prefix); if (r) return r }
  }
  // Last resort: try individual long words longest-first, stripping trailing punctuation
  const byLen = [...words].sort((a, b) => b.length - a.length)
  for (const w of byLen) {
    const clean = w.replace(/[.,!?;:'"()[\]{}]+$/, '')
    if (clean.length >= 6) { const r = findTextRange(container, clean); if (r) return r }
  }
  return null
}

function isRangeConnected(range: Range): boolean {
  try { return range.startContainer.isConnected } catch { return false }
}

/** Resolve a Range for a comment: try cache first, fall back to text search, update cache. */
export function resolveRange(
  container: HTMLElement,
  id: string,
  anchor: string,
  cache: Map<string, Range>
): Range | null {
  const cached = cache.get(id)
  if (cached && isRangeConnected(cached)) return cached
  const found = findAnchorRange(container, anchor)
  if (found) cache.set(id, found)
  return found
}

/** Apply per-color comment highlights (groups unresolved comments by color). */
export function applyCommentHighlights(
  container: HTMLElement,
  comments: Comment[],
  cache: Map<string, Range>,
  pendingAnchor: string | null
): void {
  const byColor: Record<CommentColor, Range[]> = {
    yellow: [], green: [], blue: [], purple: [], orange: [],
  }

  for (const comment of comments) {
    if (comment.resolved) continue
    if (comment.lineText === pendingAnchor) continue
    const range = resolveRange(container, comment.id, comment.lineText, cache)
    if (range) byColor[comment.color].push(range)
  }

  for (const color of ALL_COMMENT_COLORS) {
    const hlName = COMMENT_HL_PREFIX + color
    if (byColor[color].length > 0) {
      setHL(hlName, byColor[color])
    } else {
      deleteHL(hlName)
    }
  }
}

/** Apply CSS highlights for pending and submitted anchors. */
export function applyHighlights(
  container: HTMLElement,
  pendingRange: Range | null,
  pendingAnchor: string | null,
  submittedAnchors: string[],
  modalOpen: boolean,
): void {
  deleteHL(PENDING_HL)
  deleteHL(SUBMITTED_HL)

  const submittedRanges: Range[] = []
  for (const anchor of submittedAnchors) {
    if (anchor === pendingAnchor) continue
    const r = findAnchorRange(container, anchor)
    if (r) submittedRanges.push(r)
  }
  setHL(SUBMITTED_HL, submittedRanges)

  if (pendingAnchor && !modalOpen) {
    // Prefer the live Range captured at selection time; fall back to text search
    const liveOk = pendingRange !== null && isRangeConnected(pendingRange)
    const r = liveOk ? pendingRange : findAnchorRange(container, pendingAnchor)
    if (r) setHL(PENDING_HL, [r])
  }
}

/** Flash the pulse highlight; cancels any in-flight pulse first. */
export function pulseRange(range: Range, container: HTMLElement, color: CommentColor): void {
  deleteHL(PULSE_HL)
  container.style.setProperty('--pulse-start', COMMENT_TINTS_PULSE[color])
  container.style.setProperty('--pulse-end', COMMENT_TINTS[color])
  setHL(PULSE_HL, [range])
  setTimeout(() => deleteHL(PULSE_HL), 300)
}

/** Remove all CSS highlights managed by this module. */
export function clearHighlights(): void {
  deleteHL(PENDING_HL)
  deleteHL(SUBMITTED_HL)
  for (const color of ALL_COMMENT_COLORS) {
    deleteHL(COMMENT_HL_PREFIX + color)
  }
  deleteHL(PULSE_HL)
}
