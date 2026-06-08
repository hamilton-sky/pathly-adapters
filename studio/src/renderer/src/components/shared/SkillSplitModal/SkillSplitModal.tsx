import React, { useState, useEffect } from 'react'
import { ChevronUp, ChevronDown } from 'lucide-react'
import MarkdownRenderer from '../MarkdownRenderer/MarkdownRenderer'
import styles from './SkillSplitModal.module.css'

interface ProposedCell {
  id: string
  type: 'heading' | 'markdown'
  heading: string
  content: string
  checked: boolean
}

interface Props {
  filePath?: string
  fileName?: string
  rawContent?: string
  onConfirm: (cells: ProposedCell[]) => void
  onInsertOne: (rawContent: string) => void
  onClose: () => void
}

function parseMdToCells(raw: string): ProposedCell[] {
  const lines = raw.split('\n')
  const cells: ProposedCell[] = []
  let currentType: 'heading' | 'markdown' = 'markdown'
  let currentHeading = ''
  let currentLines: string[] = []

  function flush(idx: number) {
    const content = currentLines.join('\n').trim()
    if (currentHeading || content) {
      cells.push({
        id: String(idx),
        type: currentType,
        heading: currentHeading,
        content,
        checked: true,
      })
    }
  }

  let cellIndex = 0
  for (const line of lines) {
    if (line.startsWith('# ') && !line.startsWith('## ')) {
      flush(cellIndex++)
      currentType = 'heading'
      currentHeading = line.slice(2).trim()
      currentLines = []
    } else if (line.startsWith('## ')) {
      flush(cellIndex++)
      currentType = 'markdown'
      currentHeading = line.slice(3).trim()
      currentLines = []
    } else {
      currentLines.push(line)
    }
  }
  flush(cellIndex)
  return cells
}

export default function SkillSplitModal({ filePath, fileName, rawContent: rawContentProp, onConfirm, onInsertOne, onClose }: Props) {
  const [rawContent, setRawContent] = useState(rawContentProp ?? '')
  const [cells, setCells] = useState<ProposedCell[]>(() => rawContentProp ? parseMdToCells(rawContentProp) : [])

  useEffect(() => {
    if (rawContentProp !== undefined) {
      setRawContent(rawContentProp)
      setCells(parseMdToCells(rawContentProp))
    } else if (filePath) {
      window.pathly.fs.read(filePath).then((content) => {
        setRawContent(content)
        setCells(parseMdToCells(content))
      }).catch(() => {})
    }
  }, [filePath, rawContentProp])

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

  const modalTitle = fileName ? 'Add markdown as cells' : 'Split into cells'
  const modalSubtitle = fileName
    ? `Dropped ${fileName} — here's how Pathly will split it. Confirm, or insert as a single cell.`
    : "Here's how Pathly will split this cell. Confirm, or insert as a single cell."

  return (
    <div className={styles.backdrop} onClick={onClose} tabIndex={-1}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <div className={styles.modalTitle}>{modalTitle}</div>
          <div className={styles.modalSubtitle}>{modalSubtitle}</div>
        </div>

        <div className={styles.body}>
          {/* LEFT — proposed cells list */}
          <div className={styles.cellsPanel}>
            <div className={styles.panelHeader}>
              <div className={styles.panelTitle}>PROPOSED CELLS</div>
              <span className={styles.cellCountBadge}>{checkedCount} CELLS</span>
            </div>
            <div className={styles.cellsList}>
              {cells.map((cell, idx) => (
                <div
                  key={cell.id}
                  className={`${styles.cellCard} ${!cell.checked ? styles.cellCardUnchecked : ''} ${cell.type === 'heading' ? styles.cellCardHeading : styles.cellCardMarkdown}`}
                  onClick={() => toggleCell(cell.id)}
                >
                  <input
                    type="checkbox"
                    className={styles.cellCheck}
                    checked={cell.checked}
                    onChange={() => toggleCell(cell.id)}
                    onClick={e => e.stopPropagation()}
                  />
                  <div className={styles.cellBody}>
                    <span className={`${styles.typeBadge} ${cell.type === 'heading' ? styles.typeBadgeHeading : styles.typeBadgeMarkdown}`}>
                      {cell.type === 'heading' ? 'HEADING' : 'MARKDOWN'}
                    </span>
                    <div className={styles.cellHeading}>{cell.heading}</div>
                    {cell.content && (
                      <div className={styles.cellPreview}>{cell.content.split('\n')[0]}</div>
                    )}
                  </div>
                  <div className={styles.cellMoveButtons} onClick={e => e.stopPropagation()}>
                    <button
                      type="button"
                      className={styles.moveBtn}
                      title="Move up"
                      disabled={idx === 0}
                      onClick={() => moveUp(cell.id)}
                    >
                      <ChevronUp size={12} />
                    </button>
                    <button
                      type="button"
                      className={styles.moveBtn}
                      title="Move down"
                      disabled={idx === cells.length - 1}
                      onClick={() => moveDown(cell.id)}
                    >
                      <ChevronDown size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* RIGHT — live preview */}
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
          <button type="button" className={styles.btnSecondary} onClick={() => onInsertOne(rawContent)}>
            Insert as one cell
          </button>
          <button type="button" className={styles.btnCancel} onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className={styles.btnPrimary}
            disabled={checkedCount === 0}
            onClick={() => onConfirm(cells.filter(c => c.checked))}
          >
            Confirm split — {checkedCount} cells
          </button>
        </div>
      </div>
    </div>
  )
}
