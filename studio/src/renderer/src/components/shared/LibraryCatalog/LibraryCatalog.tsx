import React, { useState, useEffect, useRef } from 'react'
import { Sparkles, Search, Brain, Diamond, BookOpen, LayoutGrid, GitBranch, GripVertical, Plus, ChevronRight, ChevronsUp, MoreHorizontal, Trash2 } from 'lucide-react'
import { useCatalogData, CatalogItemData, CatalogGroup } from './useCatalogData'
import styles from './LibraryCatalog.module.css'

interface Props {
  context: 'notebook' | 'canvas'
  pathlyRoot?: string | null
  onOpenSkill?: (path: string) => void
  onOpenFlow?: (pathOrName: string) => void
  onInsertCell?: (item: CatalogItemData) => void
  onAddCells?: (item: CatalogItemData) => void
  onNewItem?: (type: CatalogGroup['type'], category?: string) => void
  onDeleteItem?: (item: CatalogItemData, type: CatalogGroup['type']) => Promise<void>
  onDeleteCategory?: (type: CatalogGroup['type'], category: string) => Promise<void>
  onNewCategory?: (type: CatalogGroup['type'], name: string) => Promise<void>
}

function GroupIcon({ icon }: { icon: CatalogGroup['icon'] }) {
  if (icon === 'brain') return <Brain size={13} />
  if (icon === 'diamond') return <Diamond size={13} />
  if (icon === 'book-open') return <BookOpen size={13} />
  if (icon === 'git-branch') return <GitBranch size={13} />
  return <LayoutGrid size={13} />
}

function leafName(item: CatalogItemData): string {
  const slash = item.name.lastIndexOf('/')
  return slash >= 0 ? item.name.slice(slash + 1) : item.name
}

interface ItemRowProps {
  item: CatalogItemData
  type: CatalogGroup['type']
  groupIcon: CatalogGroup['icon']
  context: 'notebook' | 'canvas'
  displayName?: string
  onOpenSkill?: (path: string) => void
  onOpenFlow?: (pathOrName: string) => void
  onInsertCell?: (item: CatalogItemData) => void
  onAddCells?: (item: CatalogItemData) => void
  onDeleteItem?: (item: CatalogItemData, type: CatalogGroup['type']) => void
}

function ItemRow({ item, type, groupIcon, context, displayName, onOpenSkill, onOpenFlow, onInsertCell, onAddCells, onDeleteItem }: ItemRowProps) {
  const isFragment = type === 'fragment'
  const isFlow = type === 'flow'
  const hasPath = !!item.path
  const label = displayName ?? item.name

  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  function handleDragStart(e: React.DragEvent) {
    e.dataTransfer.setData('fragment-name', item.name)
    e.dataTransfer.effectAllowed = 'copy'
  }

  function handleRowClick() {
    if (isFlow) {
      onOpenFlow?.(item.path || item.name)
      return
    }
    if (context !== 'notebook') return
    if (isFragment) {
      onInsertCell?.(item)
    } else if (hasPath) {
      onOpenSkill?.(item.path!)
    }
  }

  function handlePlusClick(e: React.MouseEvent) {
    e.stopPropagation()
    if (isFragment) {
      onInsertCell?.(item)
    } else {
      onAddCells?.(item)
    }
  }

  return (
    <div
      className={`${styles.item} ${context === 'notebook' ? styles.itemClickable : styles.itemGrabbable}`}
      draggable
      onDragStart={handleDragStart}
      onClick={handleRowClick}
      title={item.description ?? item.name}
    >
      {!isFlow && <GripVertical size={13} className={styles.itemGrip} />}
      <span className={styles.itemIcon}>
        <GroupIcon icon={groupIcon} />
      </span>
      <span className={styles.itemName}>{label}</span>

      <div className={styles.itemActions}>
        {isFlow ? (
          hasPath && (
            <button
              type="button"
              className={styles.actionBtn}
              title="Open on canvas"
              aria-label="Open on canvas"
              onClick={e => { e.stopPropagation(); onOpenFlow?.(item.path || item.name) }}
            >
              <GitBranch size={11} />
            </button>
          )
        ) : context === 'notebook' && (
          <>
            <button
              type="button"
              className={styles.actionBtn}
              title={isFragment ? 'Insert as cell' : 'Add to notebook'}
              aria-label={isFragment ? 'Insert as cell' : 'Add to notebook'}
              onClick={handlePlusClick}
            >
              <Plus size={11} />
            </button>
            {hasPath && (
              <button
                type="button"
                className={styles.actionBtn}
                title="Open to edit"
                aria-label="Open to edit"
                onClick={e => { e.stopPropagation(); onOpenSkill?.(item.path!) }}
              >
                <BookOpen size={11} />
              </button>
            )}
            {!isFragment && hasPath && (
              <div className={styles.menuWrap} ref={menuRef}>
                <button
                  type="button"
                  className={styles.actionBtn}
                  title="More options"
                  aria-label="More options"
                  onClick={e => { e.stopPropagation(); setMenuOpen(o => !o) }}
                >
                  <MoreHorizontal size={11} />
                </button>
                {menuOpen && (
                  <div className={styles.menu}>
                    <button
                      type="button"
                      className={styles.menuItem}
                      onClick={e => { e.stopPropagation(); setMenuOpen(false); onAddCells?.(item) }}
                    >
                      Split into cells
                    </button>
                  </div>
                )}
              </div>
            )}
          </>
        )}
        {onDeleteItem && (
          <button
            type="button"
            className={`${styles.actionBtn} ${styles.deleteBtn}`}
            title="Delete"
            aria-label="Delete"
            onClick={e => { e.stopPropagation(); onDeleteItem(item, type) }}
          >
            <Trash2 size={11} />
          </button>
        )}
      </div>
    </div>
  )
}

interface SubGroupProps {
  label: string
  items: CatalogItemData[]
  type: CatalogGroup['type']
  groupIcon: CatalogGroup['icon']
  context: 'notebook' | 'canvas'
  collapseKey: number
  onOpenSkill?: (path: string) => void
  onOpenFlow?: (pathOrName: string) => void
  onInsertCell?: (item: CatalogItemData) => void
  onAddCells?: (item: CatalogItemData) => void
  onDeleteItem?: (item: CatalogItemData, type: CatalogGroup['type']) => void
  onDeleteCategory?: (type: CatalogGroup['type'], category: string) => void
  onRequestDeleteCategory?: (type: CatalogGroup['type'], label: string) => void
}

function SubGroup({ label, items, type, groupIcon, context, collapseKey, onOpenSkill, onOpenFlow, onInsertCell, onAddCells, onDeleteItem, onDeleteCategory, onRequestDeleteCategory }: SubGroupProps) {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    setOpen(false)
  }, [collapseKey])

  return (
    <div className={styles.subGroup}>
      <div className={styles.subGroupHeader}>
        <button
          type="button"
          className={styles.subGroupLabel}
          onClick={() => setOpen(o => !o)}
          {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        >
          <ChevronRight size={10} className={`${styles.chevron} ${open ? styles.chevronOpen : ''}`} />
          <span className={styles.subGroupName}>{label}</span>
          <span className={styles.subGroupCount}>{items.length}</span>
        </button>
        {onDeleteCategory && (
          <button
            type="button"
            className={styles.subGroupDeleteBtn}
            title="Delete category"
            aria-label="Delete category"
            onClick={() => onRequestDeleteCategory?.(type, label)}
          >
            <Trash2 size={10} />
          </button>
        )}
      </div>
      {open && items.map(item => (
        <ItemRow
          key={item.name}
          item={item}
          type={type}
          groupIcon={groupIcon}
          context={context}
          displayName={leafName(item)}
          onOpenSkill={onOpenSkill}
          onOpenFlow={onOpenFlow}
          onInsertCell={onInsertCell}
          onAddCells={onAddCells}
          onDeleteItem={onDeleteItem}
        />
      ))}
    </div>
  )
}

interface GroupSectionProps {
  group: CatalogGroup
  context: 'notebook' | 'canvas'
  collapseKey: number
  onOpenSkill?: (path: string) => void
  onOpenFlow?: (pathOrName: string) => void
  onInsertCell?: (item: CatalogItemData) => void
  onAddCells?: (item: CatalogItemData) => void
  onNewItem?: (type: CatalogGroup['type'], category?: string) => void
  onDeleteItem?: (item: CatalogItemData, type: CatalogGroup['type']) => void
  onDeleteCategory?: (type: CatalogGroup['type'], category: string) => void
  onRequestDeleteCategory?: (type: CatalogGroup['type'], category: string) => void
}

function GroupSection({ group, context, collapseKey, onOpenSkill, onOpenFlow, onInsertCell, onAddCells, onNewItem, onDeleteItem, onDeleteCategory, onRequestDeleteCategory }: GroupSectionProps) {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    setOpen(false)
  }, [collapseKey])

  const useSubcategories = (group.type === 'skill' || group.type === 'template') &&
    group.items.some(i => i.category && i.category !== group.type)

  const groupLabelButton = (
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
  )

  const groupHeader = (
    <div className={styles.groupHeader}>
      {groupLabelButton}
      <button
        type="button"
        className={styles.groupAddBtn}
        title={`New ${group.label.toLowerCase().replace(/s$/, '')}`}
        aria-label={`New ${group.label.toLowerCase().replace(/s$/, '')}`}
        onClick={e => { e.stopPropagation(); onNewItem?.(group.type) }}
      >
        <Plus size={12} />
      </button>
    </div>
  )

  if (useSubcategories) {
    const byCategory: Record<string, CatalogItemData[]> = {}
    for (const item of group.items) {
      const cat = item.category || '_other'
      if (!byCategory[cat]) byCategory[cat] = []
      byCategory[cat].push(item)
    }
    const categories = Object.keys(byCategory).sort()

    return (
      <div>
        {groupHeader}
        {open && categories.map(cat => (
          <SubGroup
            key={cat}
            label={cat === '_other' ? 'other' : cat}
            items={byCategory[cat]}
            type={group.type}
            groupIcon={group.icon}
            context={context}
            collapseKey={collapseKey}
            onOpenSkill={onOpenSkill}
            onOpenFlow={onOpenFlow}
            onInsertCell={onInsertCell}
            onAddCells={onAddCells}
            onDeleteItem={onDeleteItem}
            onDeleteCategory={onDeleteCategory}
            onRequestDeleteCategory={onRequestDeleteCategory}
          />
        ))}
      </div>
    )
  }

  return (
    <div>
      {groupHeader}
      {open && group.items.map(item => (
        <ItemRow
          key={item.name}
          item={item}
          type={group.type}
          groupIcon={group.icon}
          context={context}
          onOpenSkill={onOpenSkill}
          onOpenFlow={onOpenFlow}
          onInsertCell={onInsertCell}
          onAddCells={onAddCells}
          onDeleteItem={onDeleteItem}
        />
      ))}
    </div>
  )
}

export default function LibraryCatalog({ context, pathlyRoot, onOpenSkill, onOpenFlow, onInsertCell, onAddCells, onNewItem, onDeleteItem, onDeleteCategory, onNewCategory }: Props) {
  const [refreshKey, setRefreshKey] = useState(0)
  const allGroups = useCatalogData(pathlyRoot, refreshKey)
  const [query, setQuery] = useState('')
  const [collapseKey, setCollapseKey] = useState(0)

  const [pendingDelete, setPendingDelete] = useState<{ item: CatalogItemData; type: CatalogGroup['type'] } | null>(null)
  const [pendingDeleteCat, setPendingDeleteCat] = useState<{ type: CatalogGroup['type']; category: string } | null>(null)

  const [newCatType, setNewCatType] = useState<CatalogGroup['type'] | null>(null)
  const [newCatName, setNewCatName] = useState('')

  function requestDelete(item: CatalogItemData, type: CatalogGroup['type']) {
    setPendingDelete({ item, type })
  }

  function requestDeleteCategory(type: CatalogGroup['type'], category: string) {
    setPendingDeleteCat({ type, category })
  }

  async function handleCreateCategory() {
    const trimmed = newCatName.trim()
    if (!trimmed || !newCatType) return
    await onNewCategory?.(newCatType, trimmed)
    setNewCatType(null)
    setNewCatName('')
    setRefreshKey(k => k + 1)
  }

  const filtered = query.trim()
    ? allGroups
        .map(g => ({
          ...g,
          items: g.items.filter(item =>
            item.name.toLowerCase().includes(query.toLowerCase()) ||
            (item.description ?? '').toLowerCase().includes(query.toLowerCase())
          ),
        }))
        .filter(g => g.items.length > 0)
    : allGroups

  return (
    <div className={styles.catalog}>
      <div className={styles.header}>
        <div className={styles.headerRow}>
          <Sparkles size={13} className={styles.headerIcon} />
          <span>Catalog</span>
        </div>
        <button
          type="button"
          className={styles.collapseBtn}
          title="Collapse all"
          aria-label="Collapse all"
          onClick={() => setCollapseKey(k => k + 1)}
        >
          <ChevronsUp size={13} />
        </button>
      </div>

      <div className={styles.searchRow}>
        <Search size={13} />
        <input
          className={styles.searchInput}
          placeholder="Search the library…"
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
      </div>

      <div className={styles.list}>
        {filtered.map(group => (
          <GroupSection
            key={group.label}
            group={group}
            context={context}
            collapseKey={collapseKey}
            onOpenSkill={onOpenSkill}
            onOpenFlow={onOpenFlow}
            onInsertCell={onInsertCell}
            onAddCells={onAddCells}
            onNewItem={onNewItem}
            onDeleteItem={onDeleteItem ? requestDelete : undefined}
            onDeleteCategory={onDeleteCategory}
            onRequestDeleteCategory={onDeleteCategory ? requestDeleteCategory : undefined}
          />
        ))}
        {filtered.length === 0 && query.trim() && (
          <div className={styles.empty}>No results for &ldquo;{query}&rdquo;</div>
        )}

        {newCatType ? (
          <div className={styles.newCatForm}>
            <input
              className={styles.newCatInput}
              value={newCatName}
              onChange={e => setNewCatName(e.target.value)}
              placeholder="Category name…"
              autoFocus
              onKeyDown={e => {
                if (e.key === 'Enter') void handleCreateCategory()
                if (e.key === 'Escape') { setNewCatType(null); setNewCatName('') }
              }}
            />
            <button type="button" className={styles.newCatConfirm} onClick={() => void handleCreateCategory()}>Create</button>
            <button type="button" className={styles.newCatCancelBtn} onClick={() => { setNewCatType(null); setNewCatName('') }}>✕</button>
          </div>
        ) : (
          <button type="button" className={styles.newCat} onClick={() => setNewCatType('skill')}>
            <Plus size={13} />
            New category
          </button>
        )}
      </div>

      {pendingDelete && (
        <div className={styles.confirmOverlay}>
          <div className={styles.confirmCard}>
            <div className={styles.confirmTitle}>Delete &ldquo;{pendingDelete.item.name}&rdquo;?</div>
            <div className={styles.confirmBody}>This action cannot be undone.</div>
            <div className={styles.confirmActions}>
              <button type="button" className={styles.confirmCancel} onClick={() => setPendingDelete(null)}>Cancel</button>
              <button
                type="button"
                className={styles.confirmDelete}
                onClick={async () => {
                  await onDeleteItem?.(pendingDelete.item, pendingDelete.type)
                  setPendingDelete(null)
                  setRefreshKey(k => k + 1)
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {pendingDeleteCat && (
        <div className={styles.confirmOverlay}>
          <div className={styles.confirmCard}>
            <div className={styles.confirmTitle}>Delete category &ldquo;{pendingDeleteCat.category}&rdquo;?</div>
            <div className={styles.confirmBody}>This action cannot be undone.</div>
            <div className={styles.confirmActions}>
              <button type="button" className={styles.confirmCancel} onClick={() => setPendingDeleteCat(null)}>Cancel</button>
              <button
                type="button"
                className={styles.confirmDelete}
                onClick={async () => {
                  await onDeleteCategory?.(pendingDeleteCat.type, pendingDeleteCat.category)
                  setPendingDeleteCat(null)
                  setRefreshKey(k => k + 1)
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
