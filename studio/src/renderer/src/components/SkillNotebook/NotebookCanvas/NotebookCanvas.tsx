import React, { useState, useEffect, useCallback } from 'react'
import { Plus } from 'lucide-react'
import { useSkillNotebookStore } from '../../../store/skillNotebookStore'
import { useUiStore } from '../../../store/uiStore'
import styles from './NotebookCanvas.module.css'
import BodyCell from '../BodyCell/BodyCell'
import FragmentCell from '../FragmentCell/FragmentCell'
import InsertZone from '../InsertZone/InsertZone'

export default function NotebookCanvas() {
  const { cells, insertFragment, insertBodyCell, moveCell, removeCell, revertBodyCell, undo, redo } = useSkillNotebookStore()
  const skillNotebookPath = useUiStore(s => s.skillNotebookPath)
  const setSkillNotebookPath = useUiStore(s => s.setSkillNotebookPath)
  const setSkillNotebookViewMode = useUiStore(s => s.setSkillNotebookViewMode)
  const loadSkill = useSkillNotebookStore(s => s.loadSkill)

  const [activeZone, setActiveZone] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [newCellId, setNewCellId] = useState<string | null>(null)

  const pathParts = skillNotebookPath ? skillNotebookPath.replace(/\\/g, '/').split('/') : []
  const skillName = pathParts[pathParts.length - 1]?.replace('.md', '') ?? ''

  useEffect(() => {
    if (skillNotebookPath) loadSkill(skillNotebookPath)
  }, [skillNotebookPath])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && !e.shiftKey && e.key === 'z') { e.preventDefault(); undo() }
      if (e.ctrlKey && e.shiftKey  && e.key === 'z') { e.preventDefault(); redo() }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [undo, redo])

  const handleOpenFragment = useCallback(async (path: string | undefined, name: string) => {
    if (path) {
      setSkillNotebookPath(path)
      setSkillNotebookViewMode('editor')
      return
    }
    const res = await fetch('http://localhost:8765/catalog/all').then(r => r.json()).catch(() => null)
    const found = res?.fragments?.find((f: { name: string; path: string }) => f.name === name)
    if (found?.path) {
      setSkillNotebookPath(found.path)
      setSkillNotebookViewMode('editor')
    }
  }, [setSkillNotebookPath, setSkillNotebookViewMode])

  function handleInsertZoneDrop(afterCellId: string | null, e: React.DragEvent) {
    const fragmentName = e.dataTransfer.getData('fragment-name')
    const fragmentPath = e.dataTransfer.getData('fragment-path') || undefined
    const cellId       = e.dataTransfer.getData('cell-id')
    if (fragmentName) {
      const id = insertFragment(fragmentName, afterCellId, fragmentPath)
      setNewCellId(id)
    } else if (cellId) {
      moveCell(cellId, afterCellId)
    }
    setActiveZone(null)
    setIsDragging(false)
  }

  function handleInsert(afterCellId: string | null) {
    const id = insertBodyCell('New section', '', afterCellId)
    setNewCellId(id)
  }

  return (
    <div
      className={styles.canvas}
      onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
      onDrop={() => setIsDragging(false)}
      onDragLeave={() => setIsDragging(false)}
    >
      <div className={styles.col}>
        {skillName && (
          <div className={styles.titleRow}>
            <h2 className={styles.nbTitle}>{skillName}</h2>
            <button
              type="button"
              className={styles.addCellBtn}
              title="Add empty cell at bottom"
              onClick={() => handleInsert(cells.length > 0 ? cells[cells.length - 1].id : null)}
            >
              <Plus size={15} />
              Add cell
            </button>
          </div>
        )}
        {skillName && (
          <p className={styles.nbMeta}>
            {cells.length} cells Â· {cells.filter(c => c.type === 'body').length} body Â· {cells.filter(c => c.type === 'fragment').length} fragments
          </p>
        )}

        <InsertZone
          afterCellId={null}
          dragActive={activeZone === 'first'}
          isDragging={isDragging}
          onDragOver={() => setActiveZone('first')}
          onDrop={e => handleInsertZoneDrop(null, e)}
          onDragLeave={() => setActiveZone(null)}
          onInsert={() => handleInsert(null)}
        />

        {cells.map((cell, idx) => (
          <React.Fragment key={cell.id}>
            {cell.type === 'body' ? (
              <BodyCell
                id={cell.id}
                heading={cell.heading}
                content={cell.content}
                isSystem={cell.isSystem === true}
                isFirst={idx === 0}
                isLast={idx === cells.length - 1}
                onMoveUp={() => { if (idx > 0) moveCell(cell.id, idx <= 1 ? null : cells[idx - 2].id) }}
                onMoveDown={() => { if (idx < cells.length - 1) moveCell(cell.id, cells[idx + 1].id) }}
                onRemove={() => removeCell(cell.id)}
                onRevert={() => revertBodyCell(cell.id)}
              />
            ) : (
              <FragmentCell
                id={cell.id}
                fragmentName={cell.fragmentName}
                category={cell.category}
                description={cell.description}
                path={cell.path}
                isNew={cell.id === newCellId}
                isFirst={idx === 0}
                isLast={idx === cells.length - 1}
                onMoveUp={() => { if (idx > 0) moveCell(cell.id, idx <= 1 ? null : cells[idx - 2].id) }}
                onMoveDown={() => { if (idx < cells.length - 1) moveCell(cell.id, cells[idx + 1].id) }}
              />
            )}
            <InsertZone
              afterCellId={cell.id}
              dragActive={activeZone === cell.id}
              isDragging={isDragging}
              onDragOver={() => setActiveZone(cell.id)}
              onDrop={e => handleInsertZoneDrop(cell.id, e)}
              onDragLeave={() => setActiveZone(null)}
              onInsert={() => handleInsert(cell.id)}
            />
          </React.Fragment>
        ))}

        {cells.length === 0 && (
          <div className={styles.empty}>Load a skill file to start editing</div>
        )}
      </div>
    </div>
  )
}
