import React, { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronDown, Check, FolderOpen, ExternalLink, FolderPlus } from 'lucide-react'
import { useStore } from '../../store'
import { openWindow, pickFolder, scaffoldPathlyWorkspace } from '../../services/pathlyApi'
import type { ProjectEntry } from '../../types'
import styles from './ProjectSelector.module.css'

interface ProjectSelectorProps {
  compact?: boolean
}

export function ProjectSelector({ compact }: ProjectSelectorProps): JSX.Element | null {
  const { projectPath, projects, setProjectPath, updateProject, addProject } = useStore()
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<{ top: number; left: number; minWidth: number } | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  // Close on outside click / Escape. The menu is portaled to <body>, so the
  // outside check must allow both the trigger and the portaled menu.
  useEffect(() => {
    if (!open) return
    function onOutside(e: MouseEvent): void {
      const t = e.target as Node
      if (menuRef.current?.contains(t) || triggerRef.current?.contains(t)) return
      setOpen(false)
    }
    function onEscape(e: KeyboardEvent): void {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onOutside)
    document.addEventListener('keydown', onEscape)
    return () => {
      document.removeEventListener('mousedown', onOutside)
      document.removeEventListener('keydown', onEscape)
    }
  }, [open])

  if (!projectPath) return null

  const current = projects.find((p) => p.path === projectPath)
  const currentName = current?.name ?? (projectPath.split(/[/\\]/).filter(Boolean).pop() ?? projectPath)
  const sorted = [...projects].sort((a, b) => (b.lastOpened ?? 0) - (a.lastOpened ?? 0))

  function toggle(): void {
    if (open) { setOpen(false); return }
    const r = triggerRef.current?.getBoundingClientRect()
    // Anchor the portaled menu to the trigger so overflow:hidden on the bar can't clip it.
    if (r) setPos({ top: r.bottom + 4, left: r.left, minWidth: Math.max(r.width, 200) })
    setOpen(true)
  }

  function switchTo(p: ProjectEntry): void {
    updateProject(p.path, { lastOpened: Date.now() })
    setProjectPath(p.path)
    setOpen(false)
  }

  function openInNewWindow(p: ProjectEntry, e: React.MouseEvent): void {
    e.stopPropagation()
    void openWindow(p.path)
    setOpen(false)
  }

  async function handleOpenFolder(): Promise<void> {
    setOpen(false)
    const folderPath = await pickFolder()
    if (!folderPath) return
    await scaffoldPathlyWorkspace(folderPath)
    const name = folderPath.split(/[/\\]/).filter(Boolean).pop() ?? folderPath
    addProject({ path: folderPath, name, lastOpened: Date.now() })
    setProjectPath(folderPath)
  }

  return (
    <div className={styles.wrap}>
      <button
        ref={triggerRef}
        type="button"
        className={`${styles.trigger} ${compact ? styles.triggerCompact : ''}`}
        aria-haspopup="menu"
        aria-label="Switch project"
        title={currentName}
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        onClick={toggle}
      >
        <FolderOpen size={13} />
        {!compact && <span className={styles.triggerLabel}>{currentName}</span>}
        <ChevronDown size={12} className={styles.chev} />
      </button>

      {open && pos && createPortal(
        <div
          ref={menuRef}
          className={styles.menu}
          role="menu"
          aria-label="Projects"
          style={{ top: pos.top, left: pos.left, minWidth: pos.minWidth }}
        >
          {sorted.map((p) => {
            const active = p.path === projectPath
            return (
              <div key={p.path} className={styles.row}>
                <button
                  type="button"
                  role="menuitemradio"
                  {...(active ? { 'aria-checked': 'true' } : { 'aria-checked': 'false' })}
                  className={`${styles.menuItem} ${active ? styles.menuItemActive : ''}`}
                  onClick={() => switchTo(p)}
                >
                  <span className={styles.check}>{active && <Check size={13} />}</span>
                  <span className={styles.itemLabel}>{p.name}</span>
                </button>
                <button
                  type="button"
                  className={styles.newWin}
                  title="Open in new window"
                  aria-label={`Open ${p.name} in new window`}
                  onClick={(e) => openInNewWindow(p, e)}
                >
                  <ExternalLink size={13} />
                </button>
              </div>
            )
          })}
          <div className={styles.divider} />
          <button type="button" role="menuitem" className={styles.menuItem} onClick={() => void handleOpenFolder()}>
            <span className={styles.check}><FolderPlus size={13} /></span>
            <span className={styles.itemLabel}>Open folder…</span>
          </button>
        </div>,
        document.body
      )}
    </div>
  )
}
