import React, { useState } from 'react'
import {
  Sparkles, Plus, Search, Brain, Diamond, BookOpen, LayoutGrid, GripVertical,
} from 'lucide-react'
import styles from './NotebookCatalog.module.css'

interface CatalogGroup {
  label: string
  items: string[]
  icon: 'brain' | 'diamond' | 'book-open' | 'layout-grid' | 'star'
}

const CATALOG_GROUPS: CatalogGroup[] = [
  { label: 'Agents',    items: ['planner', 'builder', 'reviewer', 'tester'], icon: 'brain' },
  { label: 'Fragments', items: ['role', 'procedure', 'gate'],                icon: 'diamond' },
  { label: 'Skills',    items: ['build.md', 'review.md'],                    icon: 'book-open' },
  { label: 'Templates', items: ['fsm-base'],                                 icon: 'layout-grid' },
]

function GroupIcon({ type }: { type: CatalogGroup['icon'] }) {
  if (type === 'brain') return <Brain size={15} />
  if (type === 'diamond') return <Diamond size={15} />
  if (type === 'book-open') return <BookOpen size={15} />
  return <LayoutGrid size={15} />
}

export default function NotebookCatalog() {
  const [query, setQuery] = useState('')

  const filtered = query.trim()
    ? CATALOG_GROUPS.map(g => ({
        ...g,
        items: g.items.filter(item => item.toLowerCase().includes(query.toLowerCase())),
      })).filter(g => g.items.length > 0)
    : CATALOG_GROUPS

  return (
    <div className={styles.catalog}>
      <div className={styles.header}>
        <Sparkles size={15} className={styles.headerIcon} />
        <span className={styles.headerLabel}>Catalog</span>
        <div className={styles.spacer} />
        <button type="button" className={styles.addCatBtn} aria-label="Add category">
          <Plus size={15} />
        </button>
      </div>

      <div className={styles.searchRow}>
        <Search size={14} className={styles.searchIcon} />
        <input
          className={styles.searchInput}
          placeholder="Search the library…"
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
      </div>

      <div className={styles.list}>
        {filtered.map(group => (
          <div key={group.label} className={styles.group}>
            <div className={styles.groupLabel}>
              <span className={styles.groupLabelText}>{group.label}</span>
              <div className={styles.spacer} />
              <button type="button" className={styles.groupAddBtn} aria-label={`Add to ${group.label}`}>
                <Plus size={12} />
              </button>
            </div>
            {group.items.map(item => (
              <div
                key={item}
                className={styles.item}
                draggable
                onDragStart={e => {
                  e.dataTransfer.setData('fragment-name', item)
                  e.dataTransfer.effectAllowed = 'copy'
                }}
              >
                <GripVertical size={15} className={styles.itemGrip} />
                <span className={styles.itemIcon}>
                  <GroupIcon type={group.icon} />
                </span>
                <span className={styles.itemName}>{item}</span>
                <button type="button" className={styles.itemAdd} aria-label={`Add ${item}`}>
                  <Plus size={12} />
                </button>
              </div>
            ))}
          </div>
        ))}
      </div>

      <button type="button" className={styles.newCat}>
        + New category
      </button>
    </div>
  )
}
