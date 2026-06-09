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
  if (icon === 'brain') return <Brain size={15} />
  if (icon === 'diamond') return <Diamond size={15} />
  if (icon === 'book-open') return <BookOpen size={15} />
  if (icon === 'git-branch') return <GitBranch size={15} />
  return <LayoutGrid size={15} />
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
    if (item.path) e.dataTransfer.setData('fragment-path', item.path)
    e.dataTransfer.effectAllowed = 'copy'
  }

  function handleRowClick() {
    if (isFlow) { onOpenFlow?.(item.path || item.name); return }
    if (context !== 'notebook') return
    if (hasPath) { onOpenSkill?.(item.path!) }
  }

  type MenuItem = { label: string; danger?: boolean; onClick: () => void }
  const menuItems: MenuItem[] = []

  if (isFlow) {
    if (hasPath) menuItems.push({ label: 'Open on canvas', onClick: () => { setMenuOpen(false); onOpenFlow?.(item.path || item.name) } })
  } else if (context === 'notebook') {
    menuItems.push({ label: 'Insert as cell', onClick: () => { setMenuOpen(false); onInsertCell?.(item) } })
    if (hasPath) menuItems.push({ label: 'Open to edit', onClick: () => { setMenuOpen(false); onOpenSkill?.(item.path!) } })
    if (hasPath) menuItems.push({ label: 'Split into cells', onClick: () => { setMenuOpen(false); onAddCells?.(item) } })
  }
  if (onDeleteItem) menuItems.push({ label: 'Delete', danger: true, onClick: () => { setMenuOpen(false); onDeleteItem(item, type) } })

  return (
    <div
      className={`${styles.item} ${context === 'notebook' ? styles.itemClickable : styles.itemGrabbable}`}
      draggable={context === 'canvas'}
      onDragStart={context === 'canvas' ? handleDragStart : undefined}
      onClick={handleRowClick}
      title={item.description ?? item.name}
    >
      {context === 'canvas' && !isFlow && <GripVertical size={15} className={styles.itemGrip} />}
      <span className={styles.itemIcon}><GroupIcon icon={groupIcon} /></span>
      <span className={styles.itemName}>{label}</span>

      {menuItems.length > 0 && (
        <div className={styles.itemActions}>
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
          </div>
        </div>
      )}
    </div>
  )
}

interface SubGroupProps {
  label: string
  items: CatalogItemData[]
  subCategories?: Record<string, CatalogItemData[]>
  parentCategory: string
  type: CatalogGroup['type']
  groupIcon: CatalogGroup['icon']
  context: 'notebook' | 'canvas'
  collapseKey: number
  onOpenSkill?: (path: string) => void
  onOpenFlow?: (pathOrName: string) => void
  onInsertCell?: (item: CatalogItemData) => void
  onAddCells?: (item: CatalogItemData) => void
  onDeleteItem?: (item: CatalogItemData, type: CatalogGroup['type']) => void
  onRequestDeleteCategory?: (type: CatalogGroup['type'], label: string) => void
  onNewSubcategory?: (type: CatalogGroup['type'], fullPath: string) => Promise<void>
}

function SubGroup({ label, items, subCategories, parentCategory, type, groupIcon, context, collapseKey, onOpenSkill, onOpenFlow, onInsertCell, onAddCells, onDeleteItem, onRequestDeleteCategory, onNewSubcategory }: SubGroupProps) {
  const [open, setOpen] = useState(false)
  const [subMenuOpen, setSubMenuOpen] = useState(false)
  const [showSubCatForm, setShowSubCatForm] = useState(false)
  const [subCatName, setSubCatName] = useState('')
  const subMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => { setOpen(false) }, [collapseKey])

  useEffect(() => {
    if (!subMenuOpen) return
    const handler = (e: MouseEvent) => {
      if (subMenuRef.current && !subMenuRef.current.contains(e.target as Node)) setSubMenuOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [subMenuOpen])

  async function handleCreateSubcategory() {
    const trimmed = subCatName.trim()
    if (!trimmed) return
    await onNewSubcategory?.(type, `${parentCategory}/${trimmed}`)
    setShowSubCatForm(false)
    setSubCatName('')
  }

  const totalCount = items.length + Object.values(subCategories ?? {}).reduce((s, a) => s + a.length, 0)
  const hasActions = !!(onNewSubcategory || onRequestDeleteCategory)

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
          <span className={styles.subGroupCount}>{totalCount}</span>
        </button>
        {hasActions && (
          <div className={styles.menuWrap} ref={subMenuRef}>
            <button
              type="button"
              className={styles.subGroupMenuBtn}
              title="More options"
              aria-label="More options"
              onClick={e => { e.stopPropagation(); setSubMenuOpen(o => !o) }}
            >
              <MoreHorizontal size={10} />
            </button>
            {subMenuOpen && (
              <div className={styles.menu}>
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
            placeholder="Subcategory nameâ€¦"
            autoFocus
            onKeyDown={e => {
              if (e.key === 'Enter') void handleCreateSubcategory()
              if (e.key === 'Escape') { setShowSubCatForm(false); setSubCatName('') }
            }}
          />
          <button type="button" className={styles.newCatConfirm} onClick={() => void handleCreateSubcategory()}>Create</button>
          <button type="button" className={styles.newCatCancelBtn} onClick={() => { setShowSubCatForm(false); setSubCatName('') }}>âœ•</button>
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
              onOpenSkill={onOpenSkill}
              onOpenFlow={onOpenFlow}
              onInsertCell={onInsertCell}
              onAddCells={onAddCells}
              onDeleteItem={onDeleteItem}
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
              onOpenSkill={onOpenSkill}
              onOpenFlow={onOpenFlow}
              onInsertCell={onInsertCell}
              onAddCells={onAddCells}
              onDeleteItem={onDeleteItem}
              onRequestDeleteCategory={onRequestDeleteCategory}
            />
          ))}
        </>
      )}
    </div>
  )
}

interface CatNode {
  items: CatalogItemData[]
  children: Record<string, CatalogItemData[]>
}

function buildCategoryTree(groupItems: CatalogItemData[], groupType: string): Record<string, CatNode> {
  const tree: Record<string, CatNode> = {}
  for (const item of groupItems) {
    const raw = item.category || '_other'
    const slash = raw.indexOf('/')
    if (slash >= 0) {
      const parent = raw.slice(0, slash)
      const child = raw.slice(slash + 1)
      if (!tree[parent]) tree[parent] = { items: [], children: {} }
      if (!tree[parent].children[child]) tree[parent].children[child] = []
      tree[parent].children[child].push(item)
    } else {
      const key = raw === groupType ? '_other' : raw
      if (!tree[key]) tree[key] = { items: [], children: {} }
      tree[key].items.push(item)
    }
  }
  return tree
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
  onNewCategory?: (type: CatalogGroup['type'], name: string) => Promise<void>
}

function GroupSection({ group, context, collapseKey, onOpenSkill, onOpenFlow, onInsertCell, onAddCells, onNewItem, onDeleteItem, onDeleteCategory, onRequestDeleteCategory, onNewCategory }: GroupSectionProps) {
  const [open, setOpen] = useState(false)
  const [groupMenuOpen, setGroupMenuOpen] = useState(false)
  const [showCatForm, setShowCatForm] = useState(false)
  const [catName, setCatName] = useState('')
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

  const supportsCategories = group.type === 'skill' || group.type === 'agent' || group.type === 'template'

  const useSubcategories = supportsCategories &&
    group.items.some(i => i.category && i.category !== group.type)

  async function handleCreateCategory() {
    const trimmed = catName.trim()
    if (!trimmed) return
    await onNewCategory?.(group.type, trimmed)
    setShowCatForm(false)
    setCatName('')
  }

  const singularLabel = group.label.toLowerCase().replace(/s$/, '')

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
      <div className={styles.menuWrap} ref={groupMenuRef}>
        <button
          type="button"
          className={styles.groupMenuBtn}
          title="More options"
          aria-label="More options"
          onClick={e => { e.stopPropagation(); setGroupMenuOpen(o => !o) }}
        >
          <MoreHorizontal size={12} />
        </button>
        {groupMenuOpen && (
          <div className={styles.menu}>
            <button
              type="button"
              className={styles.menuItem}
              onClick={() => { setGroupMenuOpen(false); onNewItem?.(group.type) }}
            >
              <Plus size={11} />
              New {singularLabel}
            </button>
            {supportsCategories && (
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
        placeholder={`${singularLabel} categoryâ€¦`}
        autoFocus
        onKeyDown={e => {
          if (e.key === 'Enter') void handleCreateCategory()
          if (e.key === 'Escape') { setShowCatForm(false); setCatName('') }
        }}
      />
      <button type="button" className={styles.newCatConfirm} onClick={() => void handleCreateCategory()}>Create</button>
      <button type="button" className={styles.newCatCancelBtn} onClick={() => { setShowCatForm(false); setCatName('') }}>âœ•</button>
    </div>
  )

  if (useSubcategories) {
    const tree = buildCategoryTree(group.items, group.type)
    const categories = Object.keys(tree).sort()

    return (
      <div>
        {groupHeader}
        {catForm}
        {open && categories.map(cat => (
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
            onOpenSkill={onOpenSkill}
            onOpenFlow={onOpenFlow}
            onInsertCell={onInsertCell}
            onAddCells={onAddCells}
            onDeleteItem={onDeleteItem}
            onRequestDeleteCategory={onDeleteCategory ? onRequestDeleteCategory : undefined}
            onNewSubcategory={onNewCategory}
          />
        ))}
      </div>
    )
  }

  return (
    <div>
      {groupHeader}
      {catForm}
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

const CAT_TYPES: { value: CatalogGroup['type']; label: string }[] = [
  { value: 'skill',    label: 'Skills' },
  { value: 'agent',    label: 'Agents' },
  { value: 'template', label: 'Templates' },
]

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
          <Sparkles size={15} className={styles.headerIcon} />
          <span>Catalog</span>
        </div>
        <button
          type="button"
          className={styles.collapseBtn}
          title="Collapse all"
          aria-label="Collapse all"
          onClick={() => setCollapseKey(k => k + 1)}
        >
          <ChevronsUp size={15} />
        </button>
      </div>

      <div className={styles.searchRow}>
        <Search size={15} />
        <input
          className={styles.searchInput}
          placeholder="Search the libraryâ€¦"
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
            onNewCategory={async (type, name) => {
              await onNewCategory?.(type, name)
              setRefreshKey(k => k + 1)
            }}
          />
        ))}
        {filtered.length === 0 && query.trim() && (
          <div className={styles.empty}>No results for &ldquo;{query}&rdquo;</div>
        )}

        {newCatType ? (
          <div className={styles.newCatForm}>
            <select
              className={styles.newCatSelect}
              value={newCatType}
              onChange={e => setNewCatType(e.target.value as CatalogGroup['type'])}
            >
              {CAT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
            <input
              className={styles.newCatInput}
              value={newCatName}
              onChange={e => setNewCatName(e.target.value)}
              placeholder="Category nameâ€¦"
              autoFocus
              onKeyDown={e => {
                if (e.key === 'Enter') void handleCreateCategory()
                if (e.key === 'Escape') { setNewCatType(null); setNewCatName('') }
              }}
            />
            <button type="button" className={styles.newCatConfirm} onClick={() => void handleCreateCategory()}>Create</button>
            <button type="button" className={styles.newCatCancelBtn} onClick={() => { setNewCatType(null); setNewCatName('') }}>âœ•</button>
          </div>
        ) : (
          <button type="button" className={styles.newCat} onClick={() => setNewCatType('skill')}>
            <Plus size={15} />
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
