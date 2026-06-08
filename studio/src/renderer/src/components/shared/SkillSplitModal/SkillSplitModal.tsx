import React, { useState, useEffect } from 'react'
import styles from './SkillSplitModal.module.css'

interface ProposedCell {
  id: string
  type: 'heading' | 'markdown'
  heading: string
  content: string
  checked: boolean
}

interface Props {
  filePath: string
  fileName: string
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

export default function SkillSplitModal({ filePath, fileName, onConfirm, onInsertOne, onClose }: Props) {
  const [rawContent, setRawContent] = useState('')
  const [cells, setCells] = useState<ProposedCell[]>([])

  useEffect(() => {
    window.pathly.fs.read(filePath).then((content) => {
      setRawContent(content)
      setCells(parseMdToCells(content))
    }).catch(() => {})
  }, [filePath])

  const checkedCount = cells.filter(c => c.checked).length

  function toggleCell(id: string) {
    setCells(prev => prev.map(c => c.id === id ? { ...c, checked: !c.checked } : c))
  }

  return (
    <div
      className={styles.backdrop}
      onClick={onClose}
      tabIndex={-1}
    >
      <div
        className={styles.modal}
        onClick={e => e.stopPropagation()}
      >
        <div className={styles.modalHeader}>
          <div className={styles.modalTitle}>Add markdown as cells</div>
          <div className={styles.modalSubtitle}>
            Dropped {fileName} — here&apos;s how Pathly will split it. Confirm, or insert as a single cell.
          </div>
        </div>

        <div className={styles.body}>
          <div className={styles.sourcePanel}>
            <div className={styles.panelTitle}>SOURCE FILE</div>
            <pre className={styles.sourceCode}>{rawContent}</pre>
          </div>

          <div className={styles.cellsPanel}>
            <div className={styles.panelHeader}>
              <div className={styles.panelTitle}>PROPOSED CELLS</div>
              <span className={styles.cellCountBadge}>{checkedCount} CELLS</span>
            </div>
            <div className={styles.cellsList}>
              {cells.map(cell => (
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
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className={styles.footer}>
          <button
            type="button"
            className={styles.btnSecondary}
            onClick={() => onInsertOne(rawContent)}
          >
            Insert as one cell
          </button>
          <button
            type="button"
            className={styles.btnCancel}
            onClick={onClose}
          >
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
