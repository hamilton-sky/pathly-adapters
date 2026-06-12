import { useState, useEffect } from 'react'

export type HunkStatus = 'unchanged' | 'changed' | 'added' | 'removed'

export interface DiffHunk {
  id: string
  heading: string           // '__preamble__' for content before first ##, '__para_N__' for fallback paragraphs
  originalContent: string | null
  draftContent: string | null
  status: HunkStatus
  accepted: boolean         // true = use draft version
  reviewed: boolean         // true after first card expand
}

interface Section {
  heading: string
  content: string
}

/**
 * Split markdown into sections on `## ` headings. When a document has no
 * headings at all, fall back to paragraph-level sections so the viewer shows
 * per-paragraph hunks instead of one all-or-nothing block.
 */
function parseIntoSections(text: string): Section[] {
  const parts = ('\n' + text).split(/\n(?=## )/)
  const sections = parts
    .map((p) => p.trimStart())
    .filter(Boolean)
    .map<Section>((p) => {
      const nl = p.indexOf('\n')
      if (p.startsWith('## ') && nl !== -1) {
        return { heading: p.slice(3, nl).trim(), content: p.slice(nl + 1).trim() }
      }
      return { heading: '__preamble__', content: p.trim() }
    })
    .filter((s) => s.heading || s.content)

  if (sections.every((s) => s.heading === '__preamble__')) {
    const fullText = sections.map((s) => s.content).join('\n\n')
    return fullText
      .split(/\n\n+/)
      .map((p) => p.trim())
      .filter(Boolean)
      .map((content, i) => ({ heading: `__para_${i}__`, content }))
  }

  return sections
}

/** Rebuild the final document from the user's per-hunk accept/reject choices. */
export function reconstruct(hunks: DiffHunk[]): string {
  return hunks
    .filter((h) => {
      if (h.status === 'unchanged') return true
      if (h.status === 'removed') return !h.accepted
      if (h.status === 'added') return h.accepted
      return true // 'changed' — content chosen per accepted flag below
    })
    .map((h) => {
      const content =
        h.status === 'added' || (h.status === 'changed' && h.accepted)
          ? h.draftContent ?? ''
          : h.originalContent ?? ''
      if (h.heading === '__preamble__' || h.heading.startsWith('__para_')) return content
      return `## ${h.heading}\n\n${content}`
    })
    .join('\n\n')
}

export interface UseDraftDiff {
  hunks: DiffHunk[]
  loading: boolean
  error: boolean
  toggle: (id: string) => void
  markReviewed: (id: string) => void
  setAll: (accept: boolean) => void
  acceptedCount: number
  totalChanged: number
  unreviewedCount: number
  reconstruct: () => string
}

/**
 * Loads the original + draft markdown via the Electron fs bridge, diffs them
 * into section hunks, and tracks per-hunk accept/review state. Polls every
 * 3s so the viewer surfaces an error if the draft disappears while open.
 */
export function useDraftDiff(originalPath: string, draftPath: string): UseDraftDiff {
  const [hunks, setHunks] = useState<DiffHunk[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    setLoading(true)
    setError(false)
    Promise.all([window.pathly.fs.read(originalPath), window.pathly.fs.read(draftPath)])
      .then(([orig, draft]) => {
        const origSections = parseIntoSections(orig ?? '')
        const draftSections = parseIntoSections(draft ?? '')
        const origMap = new Map(origSections.map((s) => [s.heading, s.content]))
        const draftMap = new Map(draftSections.map((s) => [s.heading, s.content]))
        const allHeadings = [
          ...new Set([...origSections.map((s) => s.heading), ...draftSections.map((s) => s.heading)]),
        ]
        const result: DiffHunk[] = allHeadings.map((heading, i) => {
          const orig_ = origMap.get(heading) ?? null
          const draft_ = draftMap.get(heading) ?? null
          let status: HunkStatus = 'unchanged'
          let accepted = false
          if (orig_ === null) {
            status = 'added'
            accepted = true
          } else if (draft_ === null) {
            status = 'removed'
            accepted = false
          } else if (orig_ !== draft_) {
            status = 'changed'
            accepted = true
          }
          return { id: String(i), heading, originalContent: orig_, draftContent: draft_, status, accepted, reviewed: false }
        })
        setHunks(result)
        setLoading(false)
      })
      .catch(() => {
        setError(true)
        setLoading(false)
      })
  }, [originalPath, draftPath])

  useEffect(() => {
    if (loading || error) return
    const interval = setInterval(() => {
      window.pathly.fs
        .read(draftPath)
        .then((content) => {
          if (content === null) setError(true)
        })
        .catch(() => setError(true))
    }, 3000)
    return () => clearInterval(interval)
  }, [loading, error, draftPath])

  function toggle(id: string): void {
    setHunks((prev) => prev.map((h) => (h.id === id ? { ...h, accepted: !h.accepted } : h)))
  }
  function markReviewed(id: string): void {
    setHunks((prev) => prev.map((h) => (h.id === id ? { ...h, reviewed: true } : h)))
  }
  /** Bulk accept/reject every changed hunk (also marks them reviewed). */
  function setAll(accept: boolean): void {
    setHunks((prev) =>
      prev.map((h) => (h.status === 'unchanged' ? h : { ...h, accepted: accept, reviewed: true })),
    )
  }

  const nonUnchanged = hunks.filter((h) => h.status !== 'unchanged')
  const acceptedCount = nonUnchanged.filter((h) => h.accepted).length
  const totalChanged = nonUnchanged.length
  const unreviewedCount = nonUnchanged.filter((h) => !h.reviewed).length

  return {
    hunks,
    loading,
    error,
    toggle,
    markReviewed,
    setAll,
    acceptedCount,
    totalChanged,
    unreviewedCount,
    reconstruct: () => reconstruct(hunks),
  }
}
