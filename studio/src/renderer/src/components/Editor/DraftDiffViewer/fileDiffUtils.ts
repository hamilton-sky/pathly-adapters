/* ─── fileDiffUtils — whole-file diff for the Code (VS Code-style) view ───
   The Cards/List views diff one section at a time. The Code view instead
   reconstructs the full original and draft documents and diffs them
   line-by-line, then shapes the result for split or unified rendering. */

import type { DiffHunk } from './useDraftDiff'
import { computeLineDiff, type DiffLine, type DiffOpType } from './diffUtils'

export type DocSide = 'original' | 'draft'

/** Rebuild a full markdown document (one side) from the section hunks. */
export function buildDocument(hunks: DiffHunk[], side: DocSide): string {
  const out: string[] = []
  for (const h of hunks) {
    const exists = side === 'original' ? h.status !== 'added' : h.status !== 'removed'
    if (!exists) continue
    if (out.length) out.push('')
    out.push(`## ${h.heading}`)
    out.push('')
    const body = (side === 'original' ? h.originalContent : h.draftContent) ?? ''
    for (const line of body.split('\n')) out.push(line)
  }
  return out.join('\n')
}

export interface FileDiffStats {
  added: number
  removed: number
}

export function diffStats(ops: DiffLine[]): FileDiffStats {
  return {
    added: ops.filter((o) => o.type === 'add').length,
    removed: ops.filter((o) => o.type === 'remove').length,
  }
}

/** Compute the line-op stream for two whole documents. */
export function fileDiffOps(original: string, draft: string): DiffLine[] {
  return computeLineDiff(original, draft)
}

type SplitCellType = 'same' | 'remove' | 'add' | 'fill'

export interface SplitRow {
  leftNo: number | null
  leftText: string | null
  leftType: SplitCellType
  rightNo: number | null
  rightText: string | null
  rightType: SplitCellType
}

/**
 * Pair consecutive removes and adds onto the same rows so changed blocks
 * line up side-by-side (the VS Code split-diff behaviour), padding the
 * shorter side with filler rows.
 */
export function toSplitRows(ops: DiffLine[]): SplitRow[] {
  const rows: SplitRow[] = []
  let leftNo = 1
  let rightNo = 1
  let removes: string[] = []
  let adds: string[] = []

  function flush(): void {
    const k = Math.max(removes.length, adds.length)
    for (let i = 0; i < k; i++) {
      const hasL = i < removes.length
      const hasR = i < adds.length
      rows.push({
        leftType: hasL ? 'remove' : 'fill',
        leftNo: hasL ? leftNo++ : null,
        leftText: hasL ? removes[i] : null,
        rightType: hasR ? 'add' : 'fill',
        rightNo: hasR ? rightNo++ : null,
        rightText: hasR ? adds[i] : null,
      })
    }
    removes = []
    adds = []
  }

  for (const op of ops) {
    if (op.type === 'same') {
      flush()
      rows.push({
        leftType: 'same',
        leftNo: leftNo++,
        leftText: op.text,
        rightType: 'same',
        rightNo: rightNo++,
        rightText: op.text,
      })
    } else if (op.type === 'remove') {
      removes.push(op.text)
    } else {
      adds.push(op.text)
    }
  }
  flush()
  return rows
}

export interface UnifiedRow {
  type: DiffOpType
  originalNo: number | null
  draftNo: number | null
  text: string
}

/** Flat single-column rows with a dual line-number gutter (unified diff). */
export function toUnifiedRows(ops: DiffLine[]): UnifiedRow[] {
  const rows: UnifiedRow[] = []
  let leftNo = 1
  let rightNo = 1
  for (const op of ops) {
    if (op.type === 'same') {
      rows.push({ type: 'same', originalNo: leftNo++, draftNo: rightNo++, text: op.text })
    } else if (op.type === 'remove') {
      rows.push({ type: 'remove', originalNo: leftNo++, draftNo: null, text: op.text })
    } else {
      rows.push({ type: 'add', originalNo: null, draftNo: rightNo++, text: op.text })
    }
  }
  return rows
}
