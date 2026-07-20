import { useState, useEffect, useRef } from 'react'
import { ChevronRight, MoreHorizontal, Plus, Trash2 } from 'lucide-react'
import { Tooltip } from '../../../ui'
import type { CatalogItemData, CatalogGroup } from '../useCatalogData'
import { leafName } from '../utils'
import { ItemRow } from '../ItemRow/ItemRow'
import type { ItemRowProps } from '../ItemRow/ItemRow'
import styles from './SubGroup.module.css'

type ItemCallbacks = Pick<ItemRowProps,
  'onOpenSkill' | 'onOpenFlow' | 'onInsertCell' | 'onAddCells' |
  'onDeleteItem' | 'onMoveItem' | 'onRenameItem'
>

export interface SubGroupProps extends ItemCallbacks {
  label: string
  items: CatalogItemData[]
  subCategories?: Record<string, CatalogItemData[]>
  parentCategory: string
  type: CatalogGroup['type']
  groupIcon: CatalogGroup['icon']
  context: 'markdown-editor' | 'canvas'
  collapseKey: number
  categories?: string[]
  onRequestDeleteCategory?: (type: CatalogGroup['type'], label: string) => void
  onNewSubcategory?: (type: CatalogGroup['type'], fullPath: string) => Promise<void>
  onRenameCategory?: (type: CatalogGroup['type'], categoryName: string, newName: string) => Promise<void>
  /** Create an item straight into THIS category (fixed-category tables: system-prompts, abilities). */
  onNewItem?: (type: CatalogGroup['type'], category?: string, name?: string) => Promise<void>
  /** Noun for the "+ New …" action (e.g. "prompt", "ability"). */
  newItemLabel?: string
}

export function SubGroup({
  label, items, subCategories, parentCategory, type, groupIcon, context,
  collapseKey, categories, onOpenSkill, onOpenFlow, onInsertCell, onAddCells,
  onDeleteItem, onRequestDeleteCategory, onNewSubcategory, onMoveItem, onRenameItem, onRenameCategory,
  onNewItem, newItemLabel,
}: SubGroupProps) {
  const [open, setOpen]                   = useState(false)
  const [subMenuOpen, setSubMenuOpen]     = useState(false)
  const [showSubCatForm, setShowSubCatForm] = useState(false)
  const [subCatName, setSubCatName]       = useState('')
  const [renaming, setRenaming]           = useState(false)
  const [renameVal, setRenameVal]         = useState('')

  const subMenuRef = useRef<HTMLDivElement>(null)
  const renameRef  = useRef<HTMLInputElement>(null)

  const isOtherBucket = parentCategory === '_other'

  useEffect(() => { setOpen(false) }, [collapseKey])

  useEffect(() => {
    if (!subMenuOpen) return
    const handler = (e: MouseEvent) => {
      if (subMenuRef.current && !subMenuRef.current.contains(e.target as Node)) setSubMenuOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [subMenuOpen])

  useEffect(() => {
    if (renaming) setTimeout(() => renameRef.current?.select(), 30)
  }, [renaming])

  async function handleCreateSubcategory() {
    const trimmed = subCatName.trim()
    if (!trimmed) return
    await onNewSubcategory?.(type, `${parentCategory}/${trimmed}`)
    setShowSubCatForm(false)
    setSubCatName('')
  }

  async function handleRenameCommit() {
    const trimmed = renameVal.trim()
    if (!trimmed) { setRenaming(false); return }
    try { await onRenameCategory?.(type, parentCategory, trimmed) } finally { setRenaming(false) }
  }

  const totalCount = items.length + Object.values(subCategories ?? {}).reduce((s, a) => s + a.length, 0)
  const canNewItem = !!onNewItem && !isOtherBucket
  const hasActions = !!(canNewItem || onNewSubcategory || onRequestDeleteCategory || (!isOtherBucket && onRenameCategory))

  return (
    <div className={styles.subGroup}>
      <div className={styles.subGroupHeader}>
        {renaming ? (
          <div className={styles.subGroupLabel}>
            <ChevronRight size={10} className={`${styles.chevron} ${open ? styles.chevronOpen : ''}`} />
            <input
              ref={renameRef}
              className={styles.renameInput}
              aria-label={`Rename category ${label}`}
              value={renameVal}
              onChange={e => setRenameVal(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') { e.preventDefault(); void handleRenameCommit() }
                if (e.key === 'Escape') setRenaming(false)
              }}
              onBlur={() => { if (renameVal.trim()) void handleRenameCommit(); else setRenaming(false) }}
            />
          </div>
        ) : (
          <button
            type="button"
            className={styles.subGroupLabel}
            onClick={() => setOpen(o => !o)}
            {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
          >
            <ChevronRight size={10} className={`${styles.chevron} ${open ? styles.chevronOpen : ''}`} />
            <span className={styles.subGroupName}>{label}</span>
            <span className={styles.subGroupCount}>{totalCount}</span>
          </button>
        )}

        {hasActions && !renaming && (
          <div className={styles.menuWrap} ref={subMenuRef}>
            <Tooltip label="More options" placement="bottom">
              <button
                type="button"
                className={styles.subGroupMenuBtn}
                aria-label="More options"
                onClick={e => { e.stopPropagation(); setSubMenuOpen(o => !o) }}
              >
                <MoreHorizontal size={10} />
              </button>
            </Tooltip>
            {subMenuOpen && (
              <div className={styles.menu}>
                {canNewItem && (
                  <button
                    type="button"
                    className={styles.menuItem}
                    onClick={() => { setSubMenuOpen(false); void onNewItem?.(type, parentCategory) }}
                  >
                    <Plus size={10} />
                    New {newItemLabel ?? 'item'}
                  </button>
                )}
                {!isOtherBucket && onRenameCategory && (
                  <button
                    type="button"
                    className={styles.menuItem}
                    onClick={() => { setSubMenuOpen(false); setOpen(true); setRenameVal(label); setRenaming(true) }}
                  >
                    Rename
                  </button>
                )}
                {onNewSubcategory && (
                  <button
                    type="button"
                    className={styles.menuItem}
                    onClick={() => { setSubMenuOpen(false); setOpen(true); setShowSubCatForm(true) }}
                  >
                    <Plus size={10} />
                    New subcategory
                  </button>
                )}
                {onRequestDeleteCategory && (
                  <button
                    type="button"
                    className={`${styles.menuItem} ${styles.menuItemDanger}`}
                    onClick={() => { setSubMenuOpen(false); onRequestDeleteCategory(type, label) }}
                  >
                    <Trash2 size={10} />
                    Delete category
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {showSubCatForm && (
        <div className={styles.newCatForm}>
          <input
            className={styles.newCatInput}
            value={subCatName}
            onChange={e => setSubCatName(e.target.value)}
            placeholder="Subcategory name…"
            autoFocus
            onKeyDown={e => {
              if (e.key === 'Enter') void handleCreateSubcategory()
              if (e.key === 'Escape') { setShowSubCatForm(false); setSubCatName('') }
            }}
          />
          <button type="button" className={styles.newCatConfirm} onClick={() => void handleCreateSubcategory()}>Create</button>
          <button type="button" className={styles.newCatCancelBtn} onClick={() => { setShowSubCatForm(false); setSubCatName('') }}>{'✕'}</button>
        </div>
      )}

      {open && (
        <>
          {items.map(item => (
            <ItemRow
              key={item.name}
              item={item}
              type={type}
              groupIcon={groupIcon}
              context={context}
              displayName={leafName(item)}
              categories={categories}
              onOpenSkill={onOpenSkill}
              onOpenFlow={onOpenFlow}
              onInsertCell={onInsertCell}
              onAddCells={onAddCells}
              onDeleteItem={onDeleteItem}
              onMoveItem={onMoveItem}
              onRenameItem={onRenameItem}
            />
          ))}
          {subCategories && Object.keys(subCategories).sort().map(subName => (
            <SubGroup
              key={subName}
              label={subName}
              items={subCategories[subName]}
              parentCategory={`${parentCategory}/${subName}`}
              type={type}
              groupIcon={groupIcon}
              context={context}
              collapseKey={collapseKey}
              categories={categories}
              onOpenSkill={onOpenSkill}
              onOpenFlow={onOpenFlow}
              onInsertCell={onInsertCell}
              onAddCells={onAddCells}
              onDeleteItem={onDeleteItem}
              onRequestDeleteCategory={onRequestDeleteCategory}
              onMoveItem={onMoveItem}
              onRenameItem={onRenameItem}
              onRenameCategory={onRenameCategory}
            />
          ))}
        </>
      )}
    </div>
  )
}
