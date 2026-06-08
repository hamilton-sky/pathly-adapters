import React, { useState, useRef, useEffect } from 'react'
import {
  Sparkles, Search, Brain, Diamond, BookOpen, LayoutGrid,
  GripVertical, Plus, Pencil, PlusSquare,
} from 'lucide-react'
import { useCatalogData, CatalogItemData, CatalogGroup } from './useCatalogData'
import styles from './LibraryCatalog.module.css'

interface Props {
  context: 'notebook' | 'canvas'
  pathlyRoot?: string
  onOpenSkill?: (path: string) => void
  onInsertCell?: (item: CatalogItemData) => void
}

function GroupIcon({ icon }: { icon: CatalogGroup['icon'] }) {
  if (icon === 'brain') return <Brain size={13} />
  if (icon === 'diamond') return <Diamond size={13} />
  if (icon === 'book-open') return <BookOpen size={13} />
  return <LayoutGrid size={13} />
}

interface ItemRowProps {
  item: CatalogItemData
  groupIcon: CatalogGroup['icon']
  context: 'notebook' | 'canvas'
  onOpenSkill?: (path: string) => void
  onInsertCell?: (item: CatalogItemData) => void
}

function ItemRow({ item, groupIcon, context, onOpenSkill, onInsertCell }: ItemRowProps) {
  const [popoverOpen, setPopoverOpen] = useState(false)
  const popoverRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!popoverOpen) return
    function handleOutside(e: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setPopoverOpen(false)
      }
    }
    document.addEventListener('mousedown', handleOutside)
    return () => document.removeEventListener('mousedown', handleOutside)
  }, [popoverOpen])

  function handleDragStart(e: React.DragEvent) {
    e.dataTransfer.setData('fragment-name', item.name)
    e.dataTransfer.effectAllowed = 'copy'
  }

  return (
    <div
      className={styles.item}
      draggable
      onDragStart={handleDragStart}
    >
      <GripVertical size={13} className={styles.itemGrip} />
      <span className={styles.itemIcon}>
        <GroupIcon icon={groupIcon} />
      </span>
      <span className={styles.itemName}>{item.name}</span>
      {context === 'notebook' && (
        <div className={styles.popoverWrap} ref={popoverRef}>
          <button
            type="button"
            className={styles.addBtn}
            aria-label={`Add ${item.name}`}
            onClick={() => setPopoverOpen(v => !v)}
          >
            <Plus size={11} />
          </button>
          {popoverOpen && (
            <div className={styles.popover} role="menu">
              <button
                type="button"
                className={styles.popoverItem}
                role="menuitem"
                onClick={() => { setPopoverOpen(false); onOpenSkill?.(item.path ?? '') }}
              >
                <Pencil size={13} className={styles.popoverIcon} />
                Open to edit
              </button>
              <button
                type="button"
                className={styles.popoverItem}
                role="menuitem"
                onClick={() => { setPopoverOpen(false); onInsertCell?.(item) }}
              >
                <PlusSquare size={13} className={styles.popoverIcon} />
                Insert as cell
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function LibraryCatalog({ context, pathlyRoot, onOpenSkill, onInsertCell }: Props) {
  const allGroups = useCatalogData(pathlyRoot)
  const [query, setQuery] = useState('')

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
        <Sparkles size={13} className={styles.headerIcon} />
        <span>Catalog</span>
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
          <div key={group.label}>
            <div className={styles.groupLabel}>
              <span className={styles.itemIcon}><GroupIcon icon={group.icon} /></span>
              {group.label}
            </div>
            {group.items.map(item => (
              <ItemRow
                key={item.name}
                item={item}
                groupIcon={group.icon}
                context={context}
                onOpenSkill={onOpenSkill}
                onInsertCell={onInsertCell}
              />
            ))}
          </div>
        ))}
        {filtered.length === 0 && query.trim() && (
          <div className={styles.empty}>No results for &ldquo;{query}&rdquo;</div>
        )}
      </div>

      <button type="button" className={styles.newCat}>
        <Plus size={13} />
        New category
      </button>
    </div>
  )
}
