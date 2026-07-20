import { useState } from 'react'
import { Sparkles, Search, Plus, ChevronsUp } from 'lucide-react'
import { useCatalogData } from './useCatalogData'
import type { CatalogItemData, CatalogGroup } from './useCatalogData'
import { Tooltip } from '../../ui'
import { leafName } from './utils'
import { GroupSection } from './GroupSection/GroupSection'
import styles from './LibraryCatalog.module.css'

interface Props {
  context: 'markdown-editor' | 'canvas'
  pathlyRoot?: string | null
  onOpenSkill?: (path: string) => void
  onOpenFlow?: (pathOrName: string) => void
  onInsertCell?: (item: CatalogItemData) => void
  onAddCells?: (item: CatalogItemData) => void
  onNewItem?: (type: CatalogGroup['type'], category?: string, name?: string) => Promise<void>
  onDeleteItem?: (item: CatalogItemData, type: CatalogGroup['type']) => Promise<void>
  onDeleteCategory?: (type: CatalogGroup['type'], category: string) => Promise<void>
  onNewCategory?: (type: CatalogGroup['type'], name: string) => Promise<void>
  onMoveItem?: (item: CatalogItemData, type: CatalogGroup['type'], newCategory: string) => Promise<void>
  onRenameItem?: (item: CatalogItemData, type: CatalogGroup['type'], newStem: string) => Promise<void>
  onRenameCategory?: (type: CatalogGroup['type'], oldName: string, newName: string) => Promise<void>
  onDuplicateItem?: (item: CatalogItemData, type: CatalogGroup['type']) => Promise<void>
}

const CAT_TYPES: { value: CatalogGroup['type']; label: string }[] = [
  { value: 'skill', label: 'Skills' },
  { value: 'agent', label: 'Agents' },
  { value: 'template', label: 'Templates' },
  { value: 'fragment', label: 'Fragments' },
]

export default function LibraryCatalog({
  context, pathlyRoot, onOpenSkill, onOpenFlow, onInsertCell, onAddCells,
  onNewItem, onDeleteItem, onDeleteCategory, onNewCategory, onMoveItem, onRenameItem, onRenameCategory,
  onDuplicateItem,
}: Props) {
  const [refreshKey, setRefreshKey]         = useState(0)
  const allGroups                           = useCatalogData(pathlyRoot, refreshKey)
  const [query, setQuery]                   = useState('')
  const [collapseKey, setCollapseKey]       = useState(0)
  const [operationError, setOperationError] = useState<string | null>(null)
  const [operationInfo, setOperationInfo]   = useState<string | null>(null)
  const [newCatType, setNewCatType]         = useState<CatalogGroup['type'] | null>(null)
  const [newCatName, setNewCatName]         = useState('')

  const [pendingDelete, setPendingDelete]       = useState<{ item: CatalogItemData; type: CatalogGroup['type'] } | null>(null)
  const [pendingDeleteCat, setPendingDeleteCat] = useState<{ type: CatalogGroup['type']; category: string } | null>(null)

  function requestDelete(item: CatalogItemData, type: CatalogGroup['type']) {
    setPendingDelete({ item, type })
  }

  function requestDeleteCategory(type: CatalogGroup['type'], category: string) {
    setPendingDeleteCat({ type, category })
  }

  function withRefresh<T extends unknown[]>(fn: (...args: T) => Promise<void>) {
    return async (...args: T) => {
      try {
        await fn(...args)
        setRefreshKey(k => k + 1)
      } catch (e: unknown) {
        setOperationError(e instanceof Error ? e.message : 'Operation failed')
      }
    }
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
        <Tooltip label="Collapse all" placement="bottom">
          <button
            type="button"
            className={styles.collapseBtn}
            aria-label="Collapse all"
            onClick={() => setCollapseKey(k => k + 1)}
          >
            <ChevronsUp size={15} />
          </button>
        </Tooltip>
      </div>

      <div className={styles.searchRow}>
        <Search size={15} />
        <input
          className={styles.searchInput}
          aria-label="Search the library"
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
            onNewItem={onNewItem ? withRefresh(async (type, category, name) => { await onNewItem(type, category, name) }) : undefined}
            onDuplicateItem={onDuplicateItem ? withRefresh(async (item, type) => { await onDuplicateItem(item, type) }) : undefined}
            onDeleteItem={onDeleteItem ? requestDelete : undefined}
            onDeleteCategory={onDeleteCategory}
            onRequestDeleteCategory={onDeleteCategory ? requestDeleteCategory : undefined}
            onNewCategory={onNewCategory ? withRefresh(async (type, name) => { await onNewCategory(type, name) }) : undefined}
            onMoveItem={onMoveItem ? withRefresh(async (item, type, cat) => { await onMoveItem(item, type, cat) }) : undefined}
            onRenameItem={onRenameItem ? async (item, type, stem) => {
              const oldName = leafName(item)
              try {
                await onRenameItem(item, type, stem)
                setRefreshKey(k => k + 1)
                setOperationInfo(`"${oldName}" renamed to "${stem}". Check plan files for any references to the old name.`)
              } catch (e: unknown) {
                setOperationError(e instanceof Error ? e.message : 'Rename failed')
              }
            } : undefined}
            onRenameCategory={onRenameCategory ? async (type, old, n) => {
              try {
                await onRenameCategory(type, old, n)
                setRefreshKey(k => k + 1)
                setOperationInfo(`Category "${old}" renamed to "${n}". Check plan files for any references to the old name.`)
              } catch (e: unknown) {
                setOperationError(e instanceof Error ? e.message : 'Category rename failed')
              }
            } : undefined}
          />
        ))}

        {filtered.length === 0 && query.trim() && (
          <div className={styles.empty}>No results for &ldquo;{query}&rdquo;</div>
        )}

        {newCatType ? (
          <div className={styles.newCatForm}>
            <select
              className={styles.newCatSelect}
              aria-label="Category type"
              value={newCatType}
              onChange={e => setNewCatType(e.target.value as CatalogGroup['type'])}
            >
              {CAT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
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
            <button type="button" className={styles.newCatCancelBtn} onClick={() => { setNewCatType(null); setNewCatName('') }}>{'✕'}</button>
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
              >Delete</button>
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
              >Delete</button>
            </div>
          </div>
        </div>
      )}

      {operationError && (
        <div className={styles.confirmOverlay}>
          <div className={styles.confirmCard}>
            <div className={styles.confirmTitle}>Error</div>
            <div className={styles.confirmBody}>{operationError}</div>
            <div className={styles.confirmActions}>
              <button type="button" className={styles.confirmCancel} onClick={() => setOperationError(null)}>OK</button>
            </div>
          </div>
        </div>
      )}

      {operationInfo && (
        <div className={styles.confirmOverlay}>
          <div className={styles.confirmCard}>
            <div className={styles.confirmTitle}>Note</div>
            <div className={styles.confirmBody}>{operationInfo}</div>
            <div className={styles.confirmActions}>
              <button type="button" className={styles.confirmCancel} onClick={() => setOperationInfo(null)}>OK</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
