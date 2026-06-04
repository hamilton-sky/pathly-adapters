import React, { useState, useEffect } from 'react'
import { useSkillNotebookStore } from '../../../store/skillNotebookStore'
import { useUiStore } from '../../../store/uiStore'
import styles from './NotebookCanvas.module.css'
import BodyCell from '../BodyCell/BodyCell'
import FragmentCell from '../FragmentCell/FragmentCell'
import InsertZone from '../InsertZone/InsertZone'

export default function NotebookCanvas() {
  const { cells, insertFragment, moveCell, undo, redo } = useSkillNotebookStore()
  const skillNotebookPath = useUiStore(s => s.skillNotebookPath)
  const loadSkill = useSkillNotebookStore(s => s.loadSkill)

  const [activeZone, setActiveZone] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [newCellId, setNewCellId] = useState<string | null>(null)

  useEffect(() => {
    if (skillNotebookPath) {
      loadSkill(skillNotebookPath)
    }
  }, [skillNotebookPath])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && !e.shiftKey && e.key === 'z') { e.preventDefault(); undo() }
      if (e.ctrlKey && e.shiftKey && e.key === 'z') { e.preventDefault(); redo() }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [undo, redo])

  const handleCanvasDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleCanvasDrop = () => {
    setIsDragging(false)
  }

  const handleCanvasDragLeave = () => {
    setIsDragging(false)
  }

  const handleInsertZoneDrop = (afterCellId: string | null, e: React.DragEvent) => {
    const fragmentName = e.dataTransfer.getData('fragment-name')
    const cellId = e.dataTransfer.getData('cell-id')
    if (fragmentName) {
      const id = insertFragment(fragmentName, afterCellId)
      setNewCellId(id)
    } else if (cellId) {
      moveCell(cellId, afterCellId)
    }
    setActiveZone(null)
    setIsDragging(false)
  }

  return (
    <div
      className={styles.canvas}
      onDragOver={handleCanvasDragOver}
      onDrop={handleCanvasDrop}
      onDragLeave={handleCanvasDragLeave}
    >
      <InsertZone
        afterCellId={null}
        dragActive={activeZone === 'first'}
        isDragging={isDragging}
        onDragOver={() => setActiveZone('first')}
        onDrop={(e) => handleInsertZoneDrop(null, e)}
        onDragLeave={() => setActiveZone(null)}
      />
      {cells.map(cell => (
        <React.Fragment key={cell.id}>
          {cell.type === 'body' ? (
            <BodyCell heading={cell.heading} content={cell.content} />
          ) : (
            <FragmentCell
              id={cell.id}
              fragmentName={cell.fragmentName}
              category={cell.category}
              description={cell.description}
              isNew={cell.id === newCellId}
            />
          )}
          <InsertZone
            afterCellId={cell.id}
            dragActive={activeZone === cell.id}
            isDragging={isDragging}
            onDragOver={() => setActiveZone(cell.id)}
            onDrop={(e) => handleInsertZoneDrop(cell.id, e)}
            onDragLeave={() => setActiveZone(null)}
          />
        </React.Fragment>
      ))}
      {cells.length === 0 && (
        <div className={styles.empty}>
          Load a skill file to start editing
        </div>
      )}
    </div>
  )
}
