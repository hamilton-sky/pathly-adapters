import { useState, useEffect, useRef } from 'react'
import { ChevronRight, MoreHorizontal, Plus, LayoutGrid } from 'lucide-react'
import { Tooltip } from '../../../ui'
import type { CatalogItemData, CatalogGroup } from '../useCatalogData'
import { GroupIcon, buildCategoryTree, FIXED_CATEGORIES } from '../utils'
import { ItemRow } from '../ItemRow/ItemRow'
import type { ItemRowProps } from '../ItemRow/ItemRow'
import { SubGroup } from '../SubGroup/SubGroup'
import styles from './GroupSection.module.css'

type ItemCallbacks = Pick<ItemRowProps,
  'onOpenSkill' | 'onOpenFlow' | 'onInsertCell' | 'onAddCells' |
  'onDeleteItem' | 'onMoveItem' | 'onRenameItem' | 'onDuplicateItem'
>

export interface GroupSectionProps extends ItemCallbacks {
  group: CatalogGroup
  context: 'markdown-editor' | 'canvas'
  collapseKey: number
  onNewItem?: (type: CatalogGroup['type'], category?: string, name?: string) => Promise<void>
  onDeleteCategory?: (type: CatalogGroup['type'], category: string) => void
  onRequestDeleteCategory?: (type: CatalogGroup['type'], category: string) => void
  onNewCategory?: (type: CatalogGroup['type'], name: string) => Promise<void>
  onRenameCategory?: (type: CatalogGroup['type'], oldName: string, newName: string) => Promise<void>
}

export function GroupSection({
  group, context, collapseKey, onOpenSkill, onOpenFlow, onInsertCell, onAddCells,
  onNewItem, onDeleteItem, onDeleteCategory, onRequestDeleteCategory, onNewCategory,
  onMoveItem, onRenameItem, onRenameCategory, onDuplicateItem,
}: GroupSectionProps) {
  const [open, setOpen]                   = useState(false)
  const [groupMenuOpen, setGroupMenuOpen] = useState(false)
  const [showCatForm, setShowCatForm]     = useState(false)
  const [catName, setCatName]             = useState('')
  const [showItemForm, setShowItemForm]   = useState(false)
  const [itemFormName, setItemFormName]   = useState('')
  const groupMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => { setOpen(false) }, [collapseKey])

  useEffect(() => {
    if (!groupMenuOpen) return
    const handler = (e: MouseEvent) => {
      if (groupMenuRef.current && !groupMenuRef.current.contains(e.target as Node)) setGroupMenuOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [groupMenuOpen])

  const supportsCategories = group.type === 'skill' || group.type === 'agent'
    || group.type === 'template' || group.type === 'fragment' || group.type === 'ability'
    || group.type === 'system'
  // Fixed-category tables (abilities, system-prompts): categories are canonical, so ALWAYS show
  // them as subfolders (even empty) and never offer "New category" — you add into the fixed set.
  const fixedCats = FIXED_CATEGORIES[group.type]
  const canCreateCategory = supportsCategories && !fixedCats

  const useSubcategories = !!fixedCats || (supportsCategories &&
    group.items.some(i => i.category && i.category !== group.type))

  async function handleCreateCategory() {
    const trimmed = catName.trim()
    if (!trimmed) return
    await onNewCategory?.(group.type, trimmed)
    setShowCatForm(false)
    setCatName('')
  }

  async function handleCreateItem() {
    const trimmed = itemFormName.trim()
    if (!trimmed) return
    await onNewItem?.(group.type, undefined, trimmed)
    setShowItemForm(false)
    setItemFormName('')
  }

  const singularLabel = group.label.toLowerCase().replace(/s$/, '')
  // Clean noun for the per-category "+ New …" affordance on fixed tables.
  const newItemNoun = group.type === 'system' ? 'prompt' : group.type === 'ability' ? 'ability' : singularLabel

  const categoryNames = supportsCategories
    ? Object.keys(buildCategoryTree(group.items, group.type, fixedCats)).filter(k => k !== '_other').sort()
    : []

  const groupHeader = (
    <div className={styles.groupHeader}>
      <button
        type="button"
        className={styles.groupLabel}
        onClick={() => setOpen(o => !o)}
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
      >
        <ChevronRight size={11} className={`${styles.chevron} ${open ? styles.chevronOpen : ''}`} />
        <span className={styles.itemIcon}><GroupIcon icon={group.icon} /></span>
        {group.label}
        <span className={styles.groupCount}>{group.items.length}</span>
      </button>

      <div className={styles.menuWrap} ref={groupMenuRef}>
        <Tooltip label="More options" placement="bottom">
          <button
            type="button"
            className={styles.groupMenuBtn}
            aria-label="More options"
            onClick={e => { e.stopPropagation(); setGroupMenuOpen(o => !o) }}
          >
            <MoreHorizontal size={12} />
          </button>
        </Tooltip>
        {groupMenuOpen && (
          <div className={styles.menu}>
            <button
              type="button"
              className={styles.menuItem}
              onClick={() => {
                setGroupMenuOpen(false)
                // Fixed-category tables open their create modal directly (it collects name +
                // category); only free-form tables need the inline name box first.
                if (fixedCats) { void onNewItem?.(group.type) }
                else { setOpen(true); setShowItemForm(true) }
              }}
            >
              <Plus size={11} />
              New {newItemNoun}
            </button>
            {canCreateCategory && (
              <button
                type="button"
                className={styles.menuItem}
                onClick={() => { setGroupMenuOpen(false); setOpen(true); setShowCatForm(true) }}
              >
                <LayoutGrid size={11} />
                New category
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )

  const catForm = showCatForm && (
    <div className={styles.newCatForm}>
      <input
        className={styles.newCatInput}
        value={catName}
        onChange={e => setCatName(e.target.value)}
        placeholder={`${singularLabel} category…`}
        autoFocus
        onKeyDown={e => {
          if (e.key === 'Enter') void handleCreateCategory()
          if (e.key === 'Escape') { setShowCatForm(false); setCatName('') }
        }}
        onBlur={() => { if (!catName.trim()) { setShowCatForm(false); setCatName('') } }}
      />
      <button type="button" className={styles.newCatConfirm} onMouseDown={e => e.preventDefault()} onClick={() => void handleCreateCategory()}>Create</button>
      <button type="button" className={styles.newCatCancelBtn} onMouseDown={e => e.preventDefault()} onClick={() => { setShowCatForm(false); setCatName('') }}>{'✕'}</button>
    </div>
  )

  const itemForm = showItemForm && (
    <div className={styles.newCatForm}>
      <input
        className={styles.newCatInput}
        value={itemFormName}
        onChange={e => setItemFormName(e.target.value)}
        placeholder={`New ${singularLabel} name…`}
        autoFocus
        onKeyDown={e => {
          if (e.key === 'Enter') void handleCreateItem()
          if (e.key === 'Escape') { setShowItemForm(false); setItemFormName('') }
        }}
        onBlur={() => { if (!itemFormName.trim()) { setShowItemForm(false); setItemFormName('') } }}
      />
      <button type="button" className={styles.newCatConfirm} onMouseDown={e => e.preventDefault()} onClick={() => void handleCreateItem()}>Create</button>
      <button type="button" className={styles.newCatCancelBtn} onMouseDown={e => e.preventDefault()} onClick={() => { setShowItemForm(false); setItemFormName('') }}>{'✕'}</button>
    </div>
  )

  if (useSubcategories) {
    const tree = buildCategoryTree(group.items, group.type, fixedCats)
    const treeCategories = Object.keys(tree).sort()
    return (
      <div className={styles.root}>
        {groupHeader}
        {catForm}
        {itemForm}
        {open && treeCategories.map(cat => (
          <SubGroup
            key={cat}
            label={cat === '_other' ? 'other' : cat}
            items={tree[cat].items}
            subCategories={Object.keys(tree[cat].children).length > 0 ? tree[cat].children : undefined}
            parentCategory={cat}
            type={group.type}
            groupIcon={group.icon}
            context={context}
            collapseKey={collapseKey}
            categories={categoryNames}
            onOpenSkill={onOpenSkill}
            onOpenFlow={onOpenFlow}
            onInsertCell={onInsertCell}
            onAddCells={onAddCells}
            onDeleteItem={onDeleteItem}
            onRequestDeleteCategory={fixedCats ? undefined : (onDeleteCategory ? onRequestDeleteCategory : undefined)}
            onNewSubcategory={fixedCats ? undefined : onNewCategory}
            onMoveItem={onMoveItem}
            onRenameItem={onRenameItem}
            onRenameCategory={fixedCats ? undefined : onRenameCategory}
            onNewItem={fixedCats ? onNewItem : undefined}
            newItemLabel={fixedCats ? newItemNoun : undefined}
            onDuplicateItem={onDuplicateItem}
          />
        ))}
      </div>
    )
  }

  return (
    <div className={styles.root}>
      {groupHeader}
      {catForm}
      {itemForm}
      {open && group.items.map(item => (
        <ItemRow
          key={item.name}
          item={item}
          type={group.type}
          groupIcon={group.icon}
          context={context}
          categories={categoryNames}
          onOpenSkill={onOpenSkill}
          onOpenFlow={onOpenFlow}
          onInsertCell={onInsertCell}
          onAddCells={onAddCells}
          onDeleteItem={onDeleteItem}
          onMoveItem={onMoveItem}
          onRenameItem={onRenameItem}
          onDuplicateItem={onDuplicateItem}
        />
      ))}
    </div>
  )
}
