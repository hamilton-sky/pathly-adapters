// Pure adapter: (lazy directory listings + UI state) → flat WsRow[].
//
// Folders first, then files; each group sorted naturally. Noise directories are
// hidden. When a filter is active, loaded folders are force-opened and only
// matches + their ancestors survive.
//
// `keyPrefix` lets the same subtree be rendered twice with independent
// expand/rename/create state (e.g. the pinned pathly/ section, prefix 'pin:').
// Row keys are `keyPrefix + fsPath`; fsPath stays real for filesystem ops.

import type { WsListing, WsRow } from './types'

export const IGNORE = new Set([
  'node_modules', '.git', '.venv', '__pycache__', 'dist', 'out',
  '.next', '.turbo', '.cache', 'coverage', '.pytest_cache', '.mypy_cache',
  '.gitkeep',
])

function byName(a: string, b: string): number {
  return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })
}

export interface BuildRowsInput {
  rootPath: string
  rootName: string
  /** Prefix for row keys — '' for the main tree, 'pin:' for the pinned copy. */
  keyPrefix: string
  /** Absolute path of pathly/features — its direct children are feature folders. */
  featuresDir: string
  listing: Record<string, WsListing>
  openKeys: Set<string>
  selectedPath: string | null
  dirtyItems: Set<string>
  editingKey: string | null
  creating: { parentKey: string; type: 'file' | 'folder' } | null
  filter: string
}

export function buildRows(input: BuildRowsInput): WsRow[] {
  const {
    rootPath, rootName, keyPrefix, featuresDir, listing, openKeys,
    selectedPath, dirtyItems, editingKey, creating, filter,
  } = input
  if (!rootPath) return []
  const q = filter.trim().toLowerCase()
  const filtering = q.length > 0
  const out: WsRow[] = []
  const K = (fsPath: string): string => keyPrefix + fsPath

  const createRow = (parentFsPath: string, level: number): WsRow => ({
    key: `__create__:${keyPrefix}${parentFsPath}`,
    fsPath: parentFsPath,
    parentFsPath,
    name: '',
    kind: creating?.type === 'folder' ? 'folder' : 'file',
    level,
    isRoot: false,
    isFolder: creating?.type === 'folder',
    isFeature: false,
    open: false,
    isActive: false,
    isDirty: false,
    editing: false,
    isCreate: true,
    createType: creating?.type ?? 'file',
  })

  const rootKey = K(rootPath)
  const rootOpen = filtering || openKeys.has(rootKey)
  out.push({
    key: rootKey, fsPath: rootPath, parentFsPath: '', name: rootName,
    kind: 'root', level: 0, isRoot: true, isFolder: true, isFeature: false, open: rootOpen,
    isActive: false, isDirty: false, editing: false,
  })
  if (creating && creating.parentKey === rootKey && rootOpen) out.push(createRow(rootPath, 1))

  const walk = (dirPath: string, level: number): void => {
    const l = listing[dirPath]
    if (!l?.loaded) return
    const dirs = l.dirs.filter((n) => !IGNORE.has(n)).sort(byName)
    const files = l.files.filter((n) => !IGNORE.has(n)).sort(byName)

    for (const name of dirs) {
      const fsPath = `${dirPath}/${name}`
      const key = K(fsPath)
      const open = filtering ? true : openKeys.has(key)
      out.push({
        key, fsPath, parentFsPath: dirPath, name,
        kind: 'folder', level, isRoot: false, isFolder: true, isFeature: dirPath === featuresDir, open,
        isActive: false, isDirty: false, editing: editingKey === key,
      })
      if (creating && creating.parentKey === key && open) out.push(createRow(fsPath, level + 1))
      if (open) walk(fsPath, level + 1)
    }
    for (const name of files) {
      const fsPath = `${dirPath}/${name}`
      const key = K(fsPath)
      out.push({
        key, fsPath, parentFsPath: dirPath, name,
        kind: 'file', level, isRoot: false, isFolder: false, isFeature: false, open: false,
        isActive: selectedPath === fsPath, isDirty: dirtyItems.has(fsPath), editing: editingKey === key,
      })
    }
  }
  if (rootOpen) walk(rootPath, 1)

  if (!filtering) return out

  // Keep filter matches + their ancestor chain (+ transient create rows).
  const byKey = new Map(out.map((r) => [r.key, r]))
  const kept = new Set<string>([rootKey])
  for (const r of out) {
    if (r.isCreate) { kept.add(r.key); continue }
    if (r.key !== rootKey && r.name.toLowerCase().includes(q)) {
      kept.add(r.key)
      let p = K(r.parentFsPath)
      while (p && byKey.has(p)) { kept.add(p); p = K(byKey.get(p)!.parentFsPath) }
    }
  }
  return out.filter((r) => kept.has(r.key))
}
