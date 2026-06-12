import { useState, useMemo } from 'react'
import type { DiffHunk } from '../useDraftDiff'
import { SplitDiff } from '../SplitDiff/SplitDiff'
import { UnifiedDiff } from '../UnifiedDiff/UnifiedDiff'
import {
  buildDocument,
  fileDiffOps,
  diffStats,
  toSplitRows,
  toUnifiedRows,
} from '../fileDiffUtils'
import styles from './CodeDiffView.module.css'

type Layout = 'split' | 'unified'

interface Props {
  hunks: DiffHunk[]
  /** Display name for the file header (defaults to the draft path's basename). */
  fileName?: string
  /** Initial sub-layout. */
  defaultLayout?: Layout
}

/**
 * File-level, VS Code-style diff. Reconstructs the whole original and draft
 * documents from the section hunks and shows them line-by-line, with a
 * Split ⇄ Unified sub-toggle. Read-only — accept/reject lives in Cards/List.
 */
export function CodeDiffView({ hunks, fileName = 'document.md', defaultLayout = 'split' }: Props) {
  const [layout, setLayout] = useState<Layout>(defaultLayout)

  const { ops, stats, splitRows, unifiedRows } = useMemo(() => {
    const original = buildDocument(hunks, 'original')
    const draft = buildDocument(hunks, 'draft')
    const o = fileDiffOps(original, draft)
    return { ops: o, stats: diffStats(o), splitRows: toSplitRows(o), unifiedRows: toUnifiedRows(o) }
  }, [hunks])

  return (
    <div className={styles.view}>
      <div className={styles.bar}>
        <span className={styles.file}>{fileName}</span>
        <span className={styles.stat}>
          <span className={styles.add}>+{stats.added}</span>
          <span className={styles.rem}>−{stats.removed}</span>
        </span>
        <span className={styles.spacer} />
        <div className={styles.seg} role="tablist" aria-label="Diff layout">
          <button type="button" role="tab" aria-selected={layout === 'split'} className={layout === 'split' ? styles.active : ''} onClick={() => setLayout('split')}>
            Split
          </button>
          <button type="button" role="tab" aria-selected={layout === 'unified'} className={layout === 'unified' ? styles.active : ''} onClick={() => setLayout('unified')}>
            Unified
          </button>
        </div>
      </div>
      <div className={styles.scroll}>
        {ops.length === 0 ? (
          <div className={styles.empty}>No differences</div>
        ) : layout === 'split' ? (
          <SplitDiff rows={splitRows} />
        ) : (
          <UnifiedDiff rows={unifiedRows} />
        )}
      </div>
    </div>
  )
}
