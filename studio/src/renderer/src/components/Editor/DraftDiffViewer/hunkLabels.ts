import type { DiffHunk, HunkStatus } from './useDraftDiff'

/** UPPERCASE status label for the badge (empty for unchanged). */
export function statusBadgeLabel(status: HunkStatus): string {
  return status === 'unchanged' ? '' : status.toUpperCase()
}

/** Verb shown on the accept/reject chip, phrased per status. */
export function acceptChipLabel(hunk: DiffHunk): string {
  if (hunk.status === 'added') return hunk.accepted ? 'Including' : 'Excluded'
  if (hunk.status === 'removed') return hunk.accepted ? 'Keeping' : 'Discarding'
  return hunk.accepted ? 'Using draft' : 'Using original'
}

/** Human heading for a hunk (handles the __preamble__ / __para_N__ sentinels). */
export function displayHeading(heading: string): string {
  const para = heading.match(/^__para_(\d+)__$/)
  if (heading === '__preamble__') return 'Preamble'
  if (para) return `Paragraph ${Number(para[1]) + 1}`
  return heading
}

/** First meaningful line of a hunk, whitespace-collapsed — for list previews. */
export function previewText(hunk: DiffHunk): string {
  const src = hunk.status === 'removed' ? hunk.originalContent ?? '' : hunk.draftContent ?? ''
  return src.replace(/\s+/g, ' ').trim()
}
