import { useEffect, useState } from 'react'
import { useStore } from '../../store'
import { useUiStore } from '../../store/uiStore'
import type { PathlyItem } from '../../types'
import { listDir, listDirs, readFile } from '../../services/pathlyApi'
import { apiFetch } from '../../lib/config'
import { WorkspaceTree } from './workspace-tree/WorkspaceTree'
import LibraryCatalog from '../shared/LibraryCatalog/LibraryCatalog'
import SkillSplitModal from '../shared/SkillSplitModal/SkillSplitModal'
import type { CatalogGroup, CatalogItemData } from '../shared/LibraryCatalog/useCatalogData'
import { useMarkdownEditorStore } from '../../store/markdownEditorStore'
import { useSidebarResize } from './shell/useSidebarResize'
import { useWindowWidth } from './shell/useWindowWidth'
import { TabBar } from './shell/TabBar'
import { BottomNav } from './shell/BottomNav'
import { BrightskyProfile } from './shell/BrightskyProfile'
import { SidebarDialogs } from './shell/SidebarDialogs'
import { IconStrip } from './shell/IconStrip'
import styles from './Sidebar.module.css'

const POPOVER_BREAKPOINT = 700

const CORE_RESOURCE_DIRS = [
  'src/pathly_data/core/flows',
  'src/pathly_data/core/skills',
  'src/pathly_data/core/agents',
  'src/pathly_data/core/templates',
]

async function hasCoreEntries(root: string, relDir: string): Promise<boolean> {
  const dir = `${root}/${relDir}`
  const [files, dirs] = await Promise.all([
    listDir(dir).catch(() => [] as string[]),
    listDirs(dir).catch(() => [] as string[]),
  ])
  return files.length > 0 || dirs.length > 0
}

async function isPathlyCoreRoot(root: string): Promise<boolean> {
  if (!root) return false
  const checks = await Promise.all(CORE_RESOURCE_DIRS.map((dir) => hasCoreEntries(root, dir)))
  return checks.every(Boolean)
}

export function Sidebar(): JSX.Element | null {
  const {
    projectPath,
    pathlyRoot,
    pathlyUserHome,
    projects,
    setPathlyUserHome,
    setPathlyRoot,
    sidebarCollapsed,
    setSidebarCollapsed,
    sidebarTab,
    setSidebarTab,
    selectedItem,
    setSelectedItem,
    setActivePanel,
    setMdEditorPath,
    mdEditorViewMode,
    setMdEditorViewMode,
    activePanel,
    lastUsedFlowPath,
    setLastUsedFlowPath,
  } = useStore()

  const insertFragment = useMarkdownEditorStore((s) => s.insertFragment)
  const insertBodyCell = useMarkdownEditorStore((s) => s.insertBodyCell)
  const mdEditorCells  = useMarkdownEditorStore((s) => s.cells)

  useEffect(() => {
    if (pathlyUserHome) return
    const fn = window.pathly.fs.userHome
    if (typeof fn !== 'function') return
    fn().then(setPathlyUserHome).catch(() => {})
  }, [pathlyUserHome, setPathlyUserHome])

  // The Library tab is Pathly's bundled/core library, not whichever saved project
  // happens to expose a partial src/pathly_data/core folder.
  useEffect(() => {
    let cancelled = false
    const probe = async (): Promise<void> => {
      const appRoot = typeof window.pathly.fs.appRoot === 'function'
        ? await window.pathly.fs.appRoot().catch(() => '')
        : ''
      const candidates = [
        ...(appRoot ? [appRoot] : []),
        ...(projectPath ? [projectPath] : []),
        ...(pathlyRoot ? [pathlyRoot] : []),
        ...projects.map((p) => p.path),
      ]
      const seen = new Set<string>()
      const unique = candidates.filter((p) => {
        if (seen.has(p)) return false
        seen.add(p)
        return true
      })
      for (const p of unique) {
        if (!cancelled && await isPathlyCoreRoot(p)) {
          if (p !== pathlyRoot) setPathlyRoot(p)
          return
        }
      }
    }
    void probe()
    return () => { cancelled = true }
  }, [pathlyRoot, projectPath, projects, setPathlyRoot])

  const activePanelUi = useUiStore((s) => s.activePanel)

  const { sidebarRef, onDragStart } = useSidebarResize()
  const windowWidth = useWindowWidth()

  const libraryOpen = sidebarTab === 'library'
  const [showFlowWizard, setShowFlowWizard]       = useState(false)
  const [showNewItemDialog, setShowNewItemDialog] = useState(false)
  const [newItemTarget, setNewItemTarget] = useState<{ type: 'skill' | 'agent' | 'template' | 'debug' | 'explore'; dir: string } | null>(null)
  const [splitModalItem, setSplitModalItem] = useState<{ path?: string; name: string } | null>(null)

  const isNarrow = windowWidth < POPOVER_BREAKPOINT

  // Open the Canvas/Flow panel, restoring the last-used flow (mirrors the old header PanelNav).
  const openCanvas = (): void => {
    setActivePanel('flow')
    if ((!selectedItem || selectedItem.type !== 'flow') && lastUsedFlowPath) {
      readFile(lastUsedFlowPath)
        .then(() =>
          setSelectedItem({
            name: lastUsedFlowPath.split('/').pop() ?? lastUsedFlowPath,
            path: lastUsedFlowPath,
            type: 'flow',
          }),
        )
        .catch(() => setLastUsedFlowPath(null))
    }
  }

  // Collapsed (wide or narrow) → icon strip. The strip carries the expand button,
  // so there's always a way to reopen now that the topbar toggle is gone.
  if (sidebarCollapsed) {
    const openTab = (tab: 'library' | 'workspace'): void => {
      setSidebarCollapsed(false)
      setSidebarTab(tab)
    }
    return (
      <IconStrip
        activePanel={activePanel}
        libraryOpen={libraryOpen}
        onExpand={() => setSidebarCollapsed(false)}
        onWorkspace={() => openTab('workspace')}
        onLibrary={() => openTab('library')}
        onCommandCenter={() => setActivePanel('command-center')}
        onMonitor={() => setActivePanel('monitor')}
        onDbExplorer={() => setActivePanel('db-explorer')}
        onMarkdownEditor={() => setActivePanel('markdown-editor')}
        onSkillComposition={() => setActivePanel('skill-composition')}
        onCanvas={openCanvas}
        onSettings={() => setActivePanel('settings')}
      />
    )
  }

  function switchTab(tab: 'library' | 'workspace'): void {
    setSidebarTab(tab)
  }

  async function deleteItemViaAPI(item: CatalogItemData, type: CatalogGroup['type']): Promise<void> {
    if (type === 'flow') {
      await apiFetch(`/flows/${encodeURIComponent(item.name)}`, { method: 'DELETE' })
    } else {
      await apiFetch(`/catalog/item?type=${type}&name=${encodeURIComponent(item.name)}`, { method: 'DELETE' })
    }
  }

  async function createNewCatalogItem(type: CatalogGroup['type'], category?: string, name?: string): Promise<void> {
    if (!name?.trim()) return
    await apiFetch('/catalog/item/new', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, name: name.trim(), category: category || '' }),
    })
  }

  async function moveCatalogItem(item: CatalogItemData, type: CatalogGroup['type'], newCategory: string): Promise<void> {
    const res = await apiFetch('/catalog/item/move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, name: item.name, newCategory }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { error?: string }
      throw new Error(body.error ?? `Move failed (${res.status})`)
    }
  }

  async function renameCatalogItem(item: CatalogItemData, type: CatalogGroup['type'], newStem: string): Promise<void> {
    const res = await apiFetch('/catalog/item/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, name: item.name, newName: newStem }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { error?: string }
      throw new Error(body.error ?? `Rename failed (${res.status})`)
    }
  }

  async function renameCatalogCategory(type: CatalogGroup['type'], oldName: string, newName: string): Promise<void> {
    const res = await apiFetch('/catalog/category/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, oldName, newName }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { error?: string }
      throw new Error(body.error ?? `Rename failed (${res.status})`)
    }
  }

  const sidebarClass = isNarrow
    ? `${styles.sidebar} ${styles.popover}`
    : styles.sidebar

  return (
    <>
    {isNarrow && (
      <div
        className={styles.backdrop}
        onClick={() => setSidebarCollapsed(true)}
        aria-hidden="true"
      />
    )}
    <div ref={sidebarRef} className={sidebarClass}>
      <TabBar libraryOpen={libraryOpen} onSwitch={switchTab} onCollapse={() => setSidebarCollapsed(true)} />

      <div className={styles.treeContainer}>
        {libraryOpen && (
          <LibraryCatalog
            context={activePanelUi === 'markdown-editor' ? 'markdown-editor' : 'canvas'}
            pathlyRoot={pathlyRoot}
            onOpenSkill={(path) => { setMdEditorPath(path); setActivePanel('markdown-editor') }}
            onOpenFlow={(pathOrName) => {
              const filename = pathOrName.replace(/\\/g, '/').split('/').pop() ?? pathOrName
              const name = filename.replace(/\.flow\.yaml$/i, '')
              setSelectedItem({ name, path: pathOrName, type: 'flow' })
              setActivePanel('flow')
              setLastUsedFlowPath(pathOrName)
            }}
            onInsertCell={(item) => {
              if (mdEditorViewMode !== 'cells') setMdEditorViewMode('cells')
              const lastCell = mdEditorCells[mdEditorCells.length - 1]
              if (item.itemType === 'fragment') {
                insertFragment(item.name, lastCell?.id ?? null)
              } else if (item.path) {
                void window.pathly.fs.read(item.path).then(raw => {
                  insertBodyCell(item.name, raw ?? '', lastCell?.id ?? null)
                }).catch(() => {
                  insertBodyCell(item.name, '', lastCell?.id ?? null)
                })
              }
            }}
            onAddCells={(item) => setSplitModalItem(item)}
            onNewItem={async (type, category, name) => {
              // Abilities browse+open only in the Library (own /skills/abilities store + the
              // ＋Ability run-gate picker); every catalog-API CRUD path guards 'ability' so the
              // new type never hits /catalog/* (which doesn't know it).
              if (type === 'ability') return
              if (type === 'flow') {
                setShowFlowWizard(true)
              } else {
                await createNewCatalogItem(type, category, name)
              }
            }}
            onDeleteItem={async (item, type) => { if (type === 'ability') return; await deleteItemViaAPI(item, type) }}
            onMoveItem={async (item, type, cat) => { if (type === 'ability') return; await moveCatalogItem(item, type, cat) }}
            onRenameItem={async (item, type, stem) => { if (type === 'ability') return; await renameCatalogItem(item, type, stem) }}
            onRenameCategory={async (type, old, n) => { if (type === 'ability') return; await renameCatalogCategory(type, old, n) }}
            onNewCategory={async (type, name) => {
              if (type === 'ability') return
              await apiFetch('/catalog/category/new', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type, name }),
              })
            }}
            onDeleteCategory={async (type, category) => {
              if (type === 'ability') return
              await apiFetch(`/catalog/category?type=${type}&name=${encodeURIComponent(category)}`, { method: 'DELETE' })
            }}
          />
        )}

        {!libraryOpen && projectPath && <WorkspaceTree />}
      </div>

      <BottomNav
        activePanel={activePanel}
        onCommandCenter={() => setActivePanel('command-center')}
        onMonitor={() => setActivePanel('monitor')}
        onDbExplorer={() => setActivePanel('db-explorer')}
        onMarkdownEditor={() => setActivePanel('markdown-editor')}
        onSkillComposition={() => setActivePanel('skill-composition')}
        onCanvas={openCanvas}
        onSettings={() => setActivePanel('settings')}
      />

      <BrightskyProfile />

      <div className={styles.resizeHandle} onMouseDown={onDragStart} role="separator" aria-orientation="vertical" aria-label="Resize sidebar" />

      <SidebarDialogs
        showFlowWizard={showFlowWizard}
        showNewItemDialog={showNewItemDialog}
        newItemTarget={newItemTarget}
        onFlowWizardClose={() => setShowFlowWizard(false)}
        onFlowWizardCreated={(filePath) => {
          setShowFlowWizard(false)
          if (filePath) {
            const item: PathlyItem = {
              name: filePath.split('/').pop() ?? '',
              path: filePath,
              type: 'flow',
            }
            setSelectedItem(item)
            setActivePanel('flow')
            setLastUsedFlowPath(filePath)
          }
        }}
        onNewItemDialogClose={() => setShowNewItemDialog(false)}
        onNewItemDialogCreated={(item) => { setShowNewItemDialog(false); setSelectedItem(item); setActivePanel('editor') }}
      />

      {splitModalItem?.path && (
        <SkillSplitModal
          filePath={splitModalItem.path}
          fileName={splitModalItem.name}
          onClose={() => setSplitModalItem(null)}
          onInsertOne={(raw) => {
            setSplitModalItem(null)
            if (mdEditorViewMode !== 'cells') setMdEditorViewMode('cells')
            const lastCell = mdEditorCells[mdEditorCells.length - 1]
            insertBodyCell(splitModalItem.name, raw, lastCell?.id ?? null)
          }}
          onConfirm={(cells) => {
            setSplitModalItem(null)
            if (mdEditorViewMode !== 'cells') setMdEditorViewMode('cells')
            let lastId = mdEditorCells[mdEditorCells.length - 1]?.id ?? null
            for (const cell of cells) {
              lastId = insertBodyCell(cell.heading, cell.content, lastId)
            }
          }}
        />
      )}
    </div>
    </>
  )
}
