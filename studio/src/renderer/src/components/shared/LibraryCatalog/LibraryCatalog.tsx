import React, { useState } from 'react'
import { Sparkles, Search, Brain, Diamond, BookOpen, LayoutGrid, GripVertical, Plus } from 'lucide-react'
import { useCatalogData, CatalogItemData, CatalogGroup } from './useCatalogData'
import styles from './LibraryCatalog.module.css'

interface Props {
  context: 'notebook' | 'canvas'
  pathlyRoot?: string | null
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
  type: CatalogGroup['type']
  groupIcon: CatalogGroup['icon']
  context: 'notebook' | 'canvas'
  onOpenSkill?: (path: string) => void
  onInsertCell?: (item: CatalogItemData) => void
}

function ItemRow({ item, type, groupIcon, context, onOpenSkill, onInsertCell }: ItemRowProps) {
  const isFragment = type === 'fragment'
  const hasPath = !!item.path

  function handleDragStart(e: React.DragEvent) {
    e.dataTransfer.setData('fragment-name', item.name)
    e.dataTransfer.effectAllowed = 'copy'
  }

  function handleRowClick() {
    if (context !== 'notebook') return
    if (isFragment) {
      onInsertCell?.(item)
    } else if (hasPath) {
      onOpenSkill?.(item.path!)
    }
  }

  return (
    <div
      className={styles.item}
      draggable
      onDragStart={handleDragStart}
      onClick={handleRowClick}
      title={item.description ?? item.name}
      style={{ cursor: context === 'notebook' ? 'pointer' : 'grab' }}
    >
      <GripVertical size={13} className={styles.itemGrip} />
      <span className={styles.itemIcon}>
        <GroupIcon icon={groupIcon} />
      </span>
      <span className={styles.itemName}>{item.name}</span>

      {context === 'notebook' && (
        <div className={styles.itemActions}>
          {/* "Add as cell" — insert fragment or open non-fragment */}
          <button
            type="button"
            className={styles.actionBtn}
            title={isFragment ? 'Insert as cell' : 'Add to notebook'}
            aria-label={isFragment ? 'Insert as cell' : 'Add to notebook'}
            onClick={e => { e.stopPropagation(); onInsertCell?.(item) }}
          >
            <Plus size={11} />
          </button>

          {/* "Open to edit" — only for items with a path */}
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
                type={group.type}
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
