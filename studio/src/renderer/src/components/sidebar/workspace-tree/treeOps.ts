// Pure async filesystem helpers for the Workspace tree. No React.
// Reads go through the services layer (listDir/listDirs); writes/deletes go
// through the window.pathly.fs IPC bridge — matching the rest of the sidebar.

import { listDir, listDirs } from '../../../services/pathlyApi'
import type { WsListing } from './types'

const fs = (): Window['pathly']['fs'] => window.pathly.fs

/** List a directory into { dirs, files } (files = entries minus subdirs). */
export async function loadListing(dir: string): Promise<WsListing> {
  const [entries, subdirs] = await Promise.all([
    listDir(dir).catch(() => [] as string[]),
    listDirs(dir).catch(() => [] as string[]),
  ])
  const dset = new Set(subdirs)
  const files = entries.filter((e) => !dset.has(e))
  return { dirs: subdirs, files, loaded: true }
}

export async function createEntry(parent: string, name: string, type: 'file' | 'folder'): Promise<void> {
  if (type === 'folder') await fs().write(`${parent}/${name}/.gitkeep`, '')
  else await fs().write(`${parent}/${name}`, '')
}

async function rmrf(path: string): Promise<void> {
  const subdirs = await listDirs(path).catch(() => [] as string[])
  const entries = await listDir(path).catch(() => [] as string[])
  const files = entries.filter((e) => !subdirs.includes(e))
  for (const f of files) await fs().delete(`${path}/${f}`).catch(() => {})
  for (const d of subdirs) await rmrf(`${path}/${d}`)
  await fs().delete(path).catch(() => {})
}

async function copyTree(src: string, dst: string): Promise<void> {
  const subdirs = await listDirs(src).catch(() => [] as string[])
  const entries = await listDir(src).catch(() => [] as string[])
  const files = entries.filter((e) => !subdirs.includes(e))
  if (files.length === 0 && subdirs.length === 0) await fs().write(`${dst}/.gitkeep`, '')
  for (const f of files) {
    const c = await fs().read(`${src}/${f}`).catch(() => '')
    await fs().write(`${dst}/${f}`, c ?? '')
  }
  for (const d of subdirs) await copyTree(`${src}/${d}`, `${dst}/${d}`)
}

export async function deleteEntry(path: string, isFolder: boolean): Promise<void> {
  if (isFolder) await rmrf(path)
  else await fs().delete(path)
}

/** Rename in place (same parent). Returns the new path. */
export async function renameEntry(path: string, parent: string, newName: string, isFolder: boolean): Promise<string> {
  const target = `${parent}/${newName}`
  if (target === path) return path
  if (isFolder) { await copyTree(path, target); await rmrf(path) }
  else { const c = await fs().read(path).catch(() => ''); await fs().write(target, c ?? ''); await fs().delete(path) }
  return target
}

/** Move into destFolder. Returns the new path, or null if the move is invalid. */
export async function moveEntry(src: string, destFolder: string, isFolder: boolean): Promise<string | null> {
  const name = src.split('/').pop() ?? ''
  if (!name) return null
  const target = `${destFolder}/${name}`
  if (target === src) return null
  if ((destFolder + '/').startsWith(src + '/')) return null // into itself or a descendant
  if (isFolder) { await copyTree(src, target); await rmrf(src) }
  else { const c = await fs().read(src).catch(() => ''); await fs().write(target, c ?? ''); await fs().delete(src) }
  return target
}
