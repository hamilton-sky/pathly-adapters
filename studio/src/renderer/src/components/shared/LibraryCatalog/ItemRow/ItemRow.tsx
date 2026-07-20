import React, { useState, useEffect, useRef } from 'react'
import { GripVertical, MoreHorizontal, ChevronLeft } from 'lucide-react'
import { Tooltip } from '../../../ui'
import { PATHLY_DRAG_MIME } from '../../../../types'
import type { PathlyCanvasDragItem, PathlySection } from '../../../../types'
import type { CatalogItemData, CatalogGroup } from '../useCatalogData'
import { GroupIcon, leafName, FIXED_CATEGORIES } from '../utils'
import styles from './ItemRow.module.css'

const SECTION_MAP: Record<string, PathlySection> = {
  skill: 'skills', agent: 'agents', template: 'templates', fragment: 'skills',
}

export interface ItemRowProps {
  item: CatalogItemData
  type: CatalogGroup['type']
  groupIcon: CatalogGroup['icon']
  context: 'markdown-editor' | 'canvas'
  displayName?: string
  categories?: string[]
  onOpenSkill?: (path: string) => void
  onOpenFlow?: (pathOrName: string) => void
  onInsertCell?: (item: CatalogItemData) => void
  onAddCells?: (item: CatalogItemData) => void
  onDeleteItem?: (item: CatalogItemData, type: CatalogGroup['type']) => void
  onMoveItem?: (item: CatalogItemData, type: CatalogGroup['type'], newCategory: string) => Promise<void>
  onRenameItem?: (item: CatalogItemData, type: CatalogGroup['type'], newStem: string) => Promise<void>
}

export function ItemRow({
  item, type, groupIcon, context, displayName, categories,
  onOpenSkill, onOpenFlow, onInsertCell, onAddCells, onDeleteItem, onMoveItem, onRenameItem,
}: ItemRowProps) {
  const isFlow     = type === 'flow'
  const isFragment = type === 'fragment'
  const hasPath    = !!item.path
  const label      = displayName ?? item.name

  const [menuOpen, setMenuOpen]     = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [renaming, setRenaming]     = useState(false)
  const [renameVal, setRenameVal]   = useState('')

  const menuRef   = useRef<HTMLDivElement>(null)
  const rowRef    = useRef<HTMLDivElement>(null)
  const renameRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
        setPickerOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  useEffect(() => {
    if (renaming) setTimeout(() => renameRef.current?.select(), 30)
  }, [renaming])

  function handleDragStart(e: React.DragEvent) {
    const payload: PathlyCanvasDragItem = {
      dragType: 'canvas',
      name: item.name,
      section: SECTION_MAP[type] ?? 'skills',
      path: item.path ? [item.path] : [],
    }
    e.dataTransfer.setData(PATHLY_DRAG_MIME, JSON.stringify(payload))
    e.dataTransfer.effectAllowed = 'copy'
  }

  function handleRowClick() {
    if (renaming) return
    if (isFlow) { onOpenFlow?.(item.path || item.name); return }
    if (context !== 'markdown-editor') return
    if (hasPath) onOpenSkill?.(item.path!)
  }

  async function handleMoveToCategory(newCategory: string) {
    setPickerOpen(false)
    setMenuOpen(false)
    await onMoveItem?.(item, type, newCategory)
    if (rowRef.current) {
      rowRef.current.classList.add(styles.itemMoveFlash)
      setTimeout(() => rowRef.current?.classList.remove(styles.itemMoveFlash), 500)
    }
  }

  async function handleRenameCommit() {
    const trimmed = renameVal.trim()
    if (!trimmed) { setRenaming(false); return }
    if (trimmed === leafName(item).replace(/\.[^.]+$/, '')) { setRenaming(false); return }
    try { await onRenameItem?.(item, type, trimmed) } finally { setRenaming(false) }
  }

  const currentCategory = (item.category && item.category !== type && item.category !== 'fragments')
    ? item.category : ''

  const hasMoveTargets = !!onMoveItem && !isFlow && (
    (categories && categories.length > 0) || currentCategory !== ''
  )

  type MenuItem = { label: string; danger?: boolean; onClick: () => void }
  const menuItems: MenuItem[] = []

  if (isFlow) {
    if (hasPath) menuItems.push({ label: 'Open on canvas', onClick: () => { setMenuOpen(false); onOpenFlow?.(item.path || item.name) } })
  } else if (context === 'markdown-editor') {
    if (item.itemType === 'fragment' || hasPath) menuItems.push({ label: 'Insert as cell', onClick: () => { setMenuOpen(false); onInsertCell?.(item) } })
    if (!isFragment && hasPath) menuItems.push({ label: 'Open to edit', onClick: () => { setMenuOpen(false); onOpenSkill?.(item.path!) } })
    if (!isFragment && hasPath) menuItems.push({ label: 'Split into cells', onClick: () => { setMenuOpen(false); onAddCells?.(item) } })
  } else {
    if (hasPath) menuItems.push({ label: 'Open', onClick: () => { setMenuOpen(false); onOpenSkill?.(item.path!) } })
  }
  // App-shipped builtins are reference-only — no rename/move/delete (there's no row to mutate).
  const mutable = !isFragment && !item.readOnly
  // Fixed-category tables (system-prompts, abilities) have a canonical, closed category set and
  // no server-side re-file path — so "Move to category…" doesn't apply to them.
  const movableType = !FIXED_CATEGORIES[type]
  if (mutable && onRenameItem && !isFlow) {
    menuItems.push({ label: 'Rename', onClick: () => {
      setMenuOpen(false)
      setRenameVal(leafName(item).replace(/\.[^.]+$/, ''))
      setRenaming(true)
    }})
  }
  if (mutable && movableType && hasMoveTargets) menuItems.push({ label: 'Move to category…', onClick: () => { setPickerOpen(true) } })
  if (mutable && onDeleteItem)   menuItems.push({ label: 'Delete', danger: true, onClick: () => { setMenuOpen(false); onDeleteItem(item, type) } })

  return (
    <div
      ref={rowRef}
      className={`${styles.item} ${context === 'markdown-editor' ? styles.itemClickable : styles.itemGrabbable}`}
      draggable={context === 'canvas' && !isFlow && !renaming}
      onDragStart={context === 'canvas' && !isFlow && !renaming ? handleDragStart : undefined}
      onClick={handleRowClick}
      title={renaming ? undefined : (item.description ?? item.name)}
    >
      {context === 'canvas' && !isFlow && <GripVertical size={15} className={styles.itemGrip} />}
      <span className={styles.itemIcon}><GroupIcon icon={groupIcon} /></span>

      {renaming ? (
        <input
          ref={renameRef}
          className={styles.renameInput}
          aria-label={`Rename ${label}`}
          value={renameVal}
          onChange={e => setRenameVal(e.target.value)}
          onClick={e => e.stopPropagation()}
          onKeyDown={e => {
            if (e.key === 'Enter') { e.preventDefault(); void handleRenameCommit() }
            if (e.key === 'Escape') setRenaming(false)
          }}
          onBlur={() => { if (renameVal.trim()) void handleRenameCommit(); else setRenaming(false) }}
        />
      ) : (
        <span className={styles.itemName}>{label}</span>
      )}

      {!renaming && menuItems.length > 0 && (
        <div className={styles.itemActions}>
          <div className={styles.menuWrap} ref={menuRef}>
            <Tooltip label="More options" placement="bottom">
              <button
                type="button"
                className={styles.actionBtn}
                aria-label="More options"
                onClick={e => { e.stopPropagation(); setMenuOpen(o => !o); setPickerOpen(false) }}
              >
                <MoreHorizontal size={11} />
              </button>
            </Tooltip>

            {menuOpen && !pickerOpen && (
              <div className={styles.menu}>
                {menuItems.map(mi => (
                  <button
                    key={mi.label}
                    type="button"
                    className={`${styles.menuItem}${mi.danger ? ` ${styles.menuItemDanger}` : ''}`}
                    onClick={e => { e.stopPropagation(); mi.onClick() }}
                  >
                    {mi.label}
                  </button>
                ))}
              </div>
            )}

            {menuOpen && pickerOpen && (
              <div className={styles.menu}>
                <button
                  type="button"
                  className={styles.menuItemBack}
                  onClick={e => { e.stopPropagation(); setPickerOpen(false) }}
                >
                  <ChevronLeft size={10} />
                  Back
                </button>
                <button
                  type="button"
                  className={currentCategory === '' ? styles.menuItemDisabled : styles.menuItem}
                  {...(currentCategory === '' ? { disabled: true } : {})}
                  onClick={e => { e.stopPropagation(); if (currentCategory !== '') void handleMoveToCategory('') }}
                >
                  {`Uncategorized${currentCategory === '' ? ' ✓' : ''}`}
                </button>
                {(categories ?? []).filter(c => c !== '_other').map(cat => (
                  <button
                    key={cat}
                    type="button"
                    className={currentCategory === cat ? styles.menuItemDisabled : styles.menuItem}
                    {...(currentCategory === cat ? { disabled: true } : {})}
                    onClick={e => { e.stopPropagation(); if (currentCategory !== cat) void handleMoveToCategory(cat) }}
                  >
                    {`${cat}${currentCategory === cat ? ' ✓' : ''}`}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
