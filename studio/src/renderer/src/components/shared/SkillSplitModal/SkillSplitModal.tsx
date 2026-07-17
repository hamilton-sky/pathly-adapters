import React, { useState, useEffect } from 'react'
import { ChevronUp, ChevronDown } from 'lucide-react'
import { Tooltip } from '../../ui'
import MarkdownRenderer from '../MarkdownRenderer/MarkdownRenderer'
import styles from './SkillSplitModal.module.css'

export interface ProposedCell {
  id: string
  type: 'heading' | 'markdown'
  heading: string
  content: string
  checked: boolean
}

/** Serialize the (checked, possibly-reordered) cells back into a markdown prompt — the
 *  inverse of parseMdToCells, used by the run gate's "use once" section config. */
export function cellsToMarkdown(cells: ProposedCell[]): string {
  return cells
    .map((c) => {
      const h = c.type === 'heading' ? `# ${c.heading}` : c.heading ? `## ${c.heading}` : ''
      return [h, c.content].filter(Boolean).join('\n\n')
    })
    .join('\n\n')
    .trim()
}

interface Props {
  filePath?: string
  fileName?: string
  rawContent?: string
  /** Override the editor-flavored heading (e.g. the run-gate "configure sections" use). */
  title?: string
  subtitle?: string
  /** Primary button label. Defaults to "Confirm split — N cells". */
  confirmLabel?: string
  /** Hide the "Insert as one cell" secondary action (not meaningful outside the editor). */
  hideInsertOne?: boolean
  onConfirm: (cells: ProposedCell[]) => void
  onInsertOne: (rawContent: string) => void
  onClose: () => void
}

function parseMdToCells(raw: string, depth: 1 | 2 | 3 = 2): ProposedCell[] {
  const lines = raw.split('\n')
  const cells: ProposedCell[] = []
  let currentType: 'heading' | 'markdown' = 'markdown'
  let currentHeading = ''
  let currentLines: string[] = []

  function flush(idx: number) {
    const content = currentLines.join('\n').trim()
    if (currentHeading || content) {
      cells.push({ id: String(idx), type: currentType, heading: currentHeading, content, checked: true })
    }
  }

  let cellIndex = 0
  for (const line of lines) {
    if (line.startsWith('# ') && !line.startsWith('## ')) {
      flush(cellIndex++)
      currentType = 'heading'
      currentHeading = line.slice(2).trim()
      currentLines = []
    } else if (depth >= 2 && line.startsWith('## ') && !line.startsWith('### ')) {
      flush(cellIndex++)
      currentType = 'markdown'
      currentHeading = line.slice(3).trim()
      currentLines = []
    } else if (depth >= 3 && line.startsWith('### ')) {
      flush(cellIndex++)
      currentType = 'markdown'
      currentHeading = line.slice(4).trim()
      currentLines = []
    } else {
      currentLines.push(line)
    }
  }
  flush(cellIndex)
  return cells
}

export default function SkillSplitModal({ filePath, fileName, rawContent: rawContentProp, title, subtitle, confirmLabel, hideInsertOne, onConfirm, onInsertOne, onClose }: Props) {
  const [rawContent, setRawContent] = useState(rawContentProp ?? '')
  const [cells, setCells] = useState<ProposedCell[]>(() => rawContentProp ? parseMdToCells(rawContentProp, 2) : [])
  const [splitDepth, setSplitDepth] = useState<1 | 2 | 3>(2)

  useEffect(() => {
    if (rawContentProp !== undefined) {
      setRawContent(rawContentProp)
      setCells(parseMdToCells(rawContentProp, splitDepth))
    } else if (filePath) {
      window.pathly.fs.read(filePath).then((content) => {
        setRawContent(content ?? '')
        setCells(parseMdToCells(content ?? '', splitDepth))
      }).catch(() => {})
    }
  }, [filePath, rawContentProp])

  useEffect(() => {
    setCells(parseMdToCells(rawContent, splitDepth))
  }, [splitDepth, rawContent])

  const checkedCount = cells.filter(c => c.checked).length
  const checkedCells = cells.filter(c => c.checked)

  function toggleCell(id: string) {
    setCells(prev => prev.map(c => c.id === id ? { ...c, checked: !c.checked } : c))
  }

  function moveUp(id: string) {
    setCells(prev => {
      const idx = prev.findIndex(c => c.id === id)
      if (idx <= 0) return prev
      const next = [...prev]
      ;[next[idx - 1], next[idx]] = [next[idx], next[idx - 1]]
      return next
    })
  }

  function moveDown(id: string) {
    setCells(prev => {
      const idx = prev.findIndex(c => c.id === id)
      if (idx < 0 || idx >= prev.length - 1) return prev
      const next = [...prev]
      ;[next[idx], next[idx + 1]] = [next[idx + 1], next[idx]]
      return next
    })
  }

  const modalTitle = title ?? (fileName ? 'Add markdown as cells' : 'Split into cells')
  const modalSubtitle =
    subtitle ??
    (fileName
      ? `Dropped ${fileName} — here's how Pathly will split it. Confirm, or insert as a single cell.`
      : "Here's how Pathly will split this cell. Confirm, or insert as a single cell.")

  return (
    <div className={styles.backdrop} onClick={onClose} tabIndex={-1}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <div className={styles.modalTitle}>{modalTitle}</div>
          <div className={styles.modalSubtitle}>{modalSubtitle}</div>
          <div className={styles.depthRow}>
            <span className={styles.depthLabel}>Split on:</span>
            {([1, 2, 3] as const).map(d => (
              <button
                key={d}
                type="button"
                className={styles.depthBtn}
                data-active={splitDepth === d}
                onClick={() => setSplitDepth(d)}
              >
                {'#'.repeat(d)} H{d}
              </button>
            ))}
          </div>
        </div>

        <div className={styles.body}>
          {/* LEFT â€" proposed cells list */}
          <div className={styles.cellsPanel}>
            <div className={styles.panelHeader}>
              <div className={styles.panelTitle}>PROPOSED CELLS</div>
              <span className={styles.cellCountBadge}>{checkedCount} CELLS</span>
            </div>
            <div className={styles.cellsList}>
              {cells.map((cell, idx) => (
                <div
                  key={cell.id}
                  className={`${styles.cellCard} ${cell.type === 'heading' ? styles.cellCardHeading : styles.cellCardBody}${!cell.checked ? ` ${styles.cellCardUnchecked}` : ''}`}
                  onClick={() => toggleCell(cell.id)}
                >
                  <div className={styles.strip}>
                    <input
                      type="checkbox"
                      className={styles.cellCheck}
                      aria-label={`Include ${cell.type} cell`}
                      checked={cell.checked}
                      onChange={() => toggleCell(cell.id)}
                      onClick={e => e.stopPropagation()}
                    />
                    <span className={styles.typeBadge}>
                      {cell.type === 'heading' ? 'HEADING' : 'BODY'}
                    </span>
                    <span className={styles.stripDiv} />
                    <Tooltip label="Move up" placement="top">
                      <button
                        type="button"
                        className={styles.moveBtn}
                        aria-label="Move up"
                        disabled={idx === 0}
                        onClick={e => { e.stopPropagation(); moveUp(cell.id) }}
                      >
                        <ChevronUp size={14} />
                      </button>
                    </Tooltip>
                    <Tooltip label="Move down" placement="top">
                      <button
                        type="button"
                        className={styles.moveBtn}
                        aria-label="Move down"
                        disabled={idx === cells.length - 1}
                        onClick={e => { e.stopPropagation(); moveDown(cell.id) }}
                      >
                        <ChevronDown size={14} />
                      </button>
                    </Tooltip>
                  </div>
                  {cell.heading && <div className={styles.cellTitle}>{cell.heading}</div>}
                  {cell.content && (
                    <div className={styles.cellPreview}>{cell.content.split('\n')[0]}</div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* RIGHT â€" live preview */}
          <div className={styles.previewPanel}>
            <div className={styles.panelTitle}>PREVIEW</div>
            <div className={styles.previewBody}>
              {checkedCells.length === 0 ? (
                <div className={styles.previewEmpty}>No cells selected</div>
              ) : (
                checkedCells.map(cell => (
                  <div key={cell.id} className={styles.previewSection}>
                    <div className={styles.previewSectionHeading}>{cell.heading.toUpperCase()}</div>
                    {cell.content && <MarkdownRenderer content={cell.content} />}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <div className={styles.footer}>
          {!hideInsertOne && (
            <button type="button" className={styles.btnSecondary} onClick={() => onInsertOne(rawContent)}>
              Insert as one cell
            </button>
          )}
          <button type="button" className={styles.btnCancel} onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className={styles.btnPrimary}
            disabled={checkedCount === 0}
            onClick={() => onConfirm(cells.filter(c => c.checked))}
          >
            {confirmLabel ?? `Confirm split — ${checkedCount} cells`}
          </button>
        </div>
      </div>
    </div>
  )
}
