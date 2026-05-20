import { useEffect, useRef, useState } from 'react'
import { FilePlus, FolderPlus, Lock, MoreHorizontal, Pencil, Plus, Trash2 } from 'lucide-react'
import type { PathlyItem, SectionState, PathlyReorgDragItem, PathlyFolderDragItem } from '../../types'
import { PATHLY_DRAG_MIME } from '../../types'
import type { PlanFolder } from '../../hooks/usePlanFiles'
import { IconButton } from '../ui'
import { SectionHeader } from './SectionHeader'
import { SubdirRow } from './SubdirRow'
import { WorkspaceItem } from './WorkspaceItem'
import { PlanSection } from './PlanSection'
import { InlineCreateInput } from './InlineCreateInput'
import { WORKSPACE_FILE_SECTIONS, PROTECTED_FILENAMES } from './constants'
import type { Section } from './types'
import { useUiStore } from '../../store/uiStore'
import styles from './Sidebar.module.css'

interface Props {
  sections: Record<string, SectionState>
  projectPath: string
  selectedItem: PathlyItem | null
  dirtyItems: Set<string>
  filter: string
  lowerFilter: string
  activeTopic: string | null
  planFolders: PlanFolder[]
  renamingPath: string | null
  renameValue: string
  inlineCreate: { target: string; parentDir: string; type: 'file' | 'folder' } | null
  onSelect: (item: PathlyItem) => void
  onToggleSection: (label: string) => void
  onToggleSubdir: (label: string, idx: number) => void
  onActivePanel: (p: 'plan' | 'editor' | 'flow' | 'monitor' | 'settings') => void
  onCreateTopLevelFolder: (e: React.MouseEvent<HTMLButtonElement>) => void
  onCreatePlanFile: (e: React.MouseEvent<HTMLButtonElement>) => void
  onInlineCreateFile: (section: { label: string; type: string; dir: string }, e: React.MouseEvent<HTMLButtonElement>) => void
  onInlineCreateFolder: (section: { label: string; type: string; dir: string }, e: React.MouseEvent<HTMLButtonElement>) => void
  onNewPlan: (e: React.MouseEvent<HTMLButtonElement>) => void
  onInlineCreateSubmit: (name: string) => void
  onInlineCreateCancel: () => void
  onRenameChange: (v: string) => void
  onRenameCommit: (item: PathlyItem, itemDir: string) => void
  onRenameCancel: () => void
  onStartRename: (item: PathlyItem, itemDir: string) => void
  onStartDelete: (item: PathlyItem) => void
  planOpen: boolean
  onTogglePlan: () => void
  onToggleFolder: (name: string) => void
  onFolderClick: (name: string) => void
  onReorgDrop?: (sourcePath: string, targetDir: string, sectionId: string) => void
  onRenameFolder?: (oldPath: string, newName: string) => void
  onDeleteFolder?: (folderPath: string) => void
  onMoveFolder?: (sourcePath: string, targetSectionDir: string) => void
  onDeletePlanFolder?: (folderPath: string) => void
  onDeleteCustomSection?: (sectionDir: string) => void
  onInlineCreateFileInFolder?: (folderPath: string) => void
  customWorkspaceSections?: Section[]
}

export function WorkspacePanel(props: Props): JSX.Element {
  const {
    sections, projectPath, selectedItem, dirtyItems,
    filter, lowerFilter, activeTopic, planFolders,
    renamingPath, renameValue, inlineCreate,
    onSelect, onToggleSection, onToggleSubdir,
    onCreateTopLevelFolder, onCreatePlanFile,
    onInlineCreateFile, onInlineCreateFolder, onNewPlan,
    onInlineCreateSubmit, onInlineCreateCancel,
    onRenameChange, onRenameCommit, onRenameCancel,
    onStartRename, onStartDelete,
    planOpen, onTogglePlan, onToggleFolder, onFolderClick,
    onReorgDrop, onRenameFolder, onDeleteFolder, onMoveFolder, onDeletePlanFolder,
    onDeleteCustomSection, onInlineCreateFileInFolder, customWorkspaceSections = [],
  } = props

  const { userLockedFolders, toggleFolderLock } = useUiStore()
  const [dragOverFolder, setDragOverFolder] = useState<string | null>(null)
  const [dragOverSection, setDragOverSection] = useState<string | null>(null)
  const [renamingFolderPath, setRenamingFolderPath] = useState<string | null>(null)
  const [renamingFolderValue, setRenamingFolderValue] = useState('')
  const [customSectionMenuOpen, setCustomSectionMenuOpen] = useState<string | null>(null)
  const customSectionMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!customSectionMenuOpen) return
    function onOutside(e: MouseEvent): void {
      if (customSectionMenuRef.current && !customSectionMenuRef.current.contains(e.target as Node)) {
        setCustomSectionMenuOpen(null)
      }
    }
    function onEsc(e: KeyboardEvent): void { if (e.key === 'Escape') setCustomSectionMenuOpen(null) }
    document.addEventListener('mousedown', onOutside)
    document.addEventListener('keydown', onEsc)
    return () => { document.removeEventListener('mousedown', onOutside); document.removeEventListener('keydown', onEsc) }
  }, [customSectionMenuOpen])

  return (
    <>
      <div className={styles.workspaceHeader}>
        <span className={styles.workspaceHeaderLabel}>WORKSPACE</span>
        <div className={styles.workspaceHeaderActions}>
          <IconButton onClick={onCreateTopLevelFolder} title="New folder in workspace root">
            <FolderPlus size={12} />
          </IconButton>
        </div>
      </div>

      {inlineCreate?.target === 'workspace-root' && (
        <InlineCreateInput
          type={inlineCreate.type}
          onCommit={onInlineCreateSubmit}
          onCancel={onInlineCreateCancel}
        />
      )}

      <PlanSection
        planFolders={planFolders}
        selectedItem={selectedItem}
        dirtyItems={dirtyItems}
        lowerFilter={lowerFilter}
        activeTopic={activeTopic}
        renamingPath={renamingPath}
        renameValue={renameValue}
        planOpen={planOpen}
        inlineCreate={inlineCreate}
        onTogglePlan={onTogglePlan}
        onToggleFolder={onToggleFolder}
        onFolderClick={onFolderClick}
        onNewPlan={onNewPlan}
        onCreatePlanFile={onCreatePlanFile}
        onInlineCreateSubmit={onInlineCreateSubmit}
        onInlineCreateCancel={onInlineCreateCancel}
        onDeletePlanFolder={onDeletePlanFolder}
        onSelect={onSelect}
        onRenameChange={onRenameChange}
        onRenameCommit={onRenameCommit}
        onRenameCancel={onRenameCancel}
        onStartRename={onStartRename}
        onStartDelete={onStartDelete}
      />

      {WORKSPACE_FILE_SECTIONS.map((section) => {
        const state = sections[section.label]
        if (!state) return null
        if (state.subdirs === null) return null
        const subdirs = state.subdirs ?? []
        const hasMatch = !filter || subdirs.some((sd) => sd.files.some((f) => f.name.toLowerCase().includes(lowerFilter)))
        if (!hasMatch) return null
        const sectionTargetDir = `${projectPath}/${section.dir}`
        return (
          <div
            key={section.label}
            className={dragOverSection === section.label ? styles.subdirRowDragOver : undefined}
            onDragOver={(e) => {
              if (e.dataTransfer.types.includes(PATHLY_DRAG_MIME)) {
                e.preventDefault()
                e.dataTransfer.dropEffect = 'move'
                setDragOverSection(section.label)
              }
            }}
            onDragLeave={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragOverSection(null)
            }}
            onDrop={(e) => {
              setDragOverSection(null)
              const raw = e.dataTransfer.getData(PATHLY_DRAG_MIME)
              if (!raw) return
              try {
                const payload = JSON.parse(raw) as PathlyFolderDragItem
                if (payload.dragType !== 'reorg-folder') return
                if (payload.sectionDir === sectionTargetDir) return
                onMoveFolder?.(payload.sourcePath, sectionTargetDir)
              } catch { /* ignore */ }
            }}
          >
            <SectionHeader
              label={section.label}
              open={state.open}
              onToggle={() => onToggleSection(section.label)}
              actionsLeft={
                <IconButton
                  onClick={(e) => onInlineCreateFolder(section, e)}
                  title="New folder"
                >
                  <FolderPlus size={12} />
                </IconButton>
              }
              actions={
                <IconButton
                  onClick={(e) => onInlineCreateFile(section, e)}
                  title="New file"
                >
                  <Plus size={12} />
                </IconButton>
              }
            />
            {state.open && (
              <div>
                {inlineCreate?.target === section.dir && (
                  <InlineCreateInput
                    type={inlineCreate.type}
                    onCommit={onInlineCreateSubmit}
                    onCancel={onInlineCreateCancel}
                  />
                )}
                {subdirs.map((subdir, idx) => {
                  const filteredFiles = filter ? subdir.files.filter((f) => f.name.toLowerCase().includes(lowerFilter)) : subdir.files
                  if (filter && filteredFiles.length === 0) return null
                  const itemDir = `${projectPath}/${section.dir}/${subdir.name}`
                  const folderKey = `${projectPath}/${section.dir}/${subdir.name}`
                  return (
                    <div key={subdir.name}>
                      <SubdirRow
                        name={subdir.name}
                        open={subdir.open}
                        onToggle={() => { if (renamingFolderPath !== folderKey) onToggleSubdir(section.label, idx) }}
                        isSystemFolder={subdir.files.some(f => PROTECTED_FILENAMES.has(f.name))}
                        isUserLocked={userLockedFolders.has(folderKey)}
                        onToggleFolderLock={() => toggleFolderLock(folderKey)}
                        folderPath={folderKey}
                        isDragOver={dragOverFolder === folderKey}
                        onDragOver={() => setDragOverFolder(folderKey)}
                        onDrop={(e) => {
                          setDragOverFolder(null)
                          const raw = e.dataTransfer.getData(PATHLY_DRAG_MIME)
                          if (!raw) return
                          try {
                            const payload = JSON.parse(raw) as PathlyReorgDragItem
                            if (payload.dragType !== 'reorg') return
                            if ((payload.section as string) !== (section.type as string)) return
                            onReorgDrop?.(payload.sourcePath, `${projectPath}/${section.dir}/${subdir.name}`, section.type)
                          } catch { /* ignore malformed payload */ }
                        }}
                        onDragLeave={() => setDragOverFolder(null)}
                        renamingThis={renamingFolderPath === folderKey}
                        renameValue={renamingFolderValue}
                        onRenameChange={setRenamingFolderValue}
                        onRenameCommit={() => {
                          const v = renamingFolderValue
                          setRenamingFolderPath(null)
                          onRenameFolder?.(folderKey, v)
                        }}
                        onRenameCancel={() => setRenamingFolderPath(null)}
                        onStartRenameFolder={() => {
                          setRenamingFolderValue(subdir.name)
                          setRenamingFolderPath(folderKey)
                        }}
                        onStartDeleteFolder={
                          !userLockedFolders.has(folderKey)
                            ? () => onDeleteFolder?.(folderKey)
                            : undefined
                        }
                        onCreateFileInFolder={() => {
                          if (!subdir.open) onToggleSubdir(section.label, idx)
                          onInlineCreateFileInFolder?.(folderKey)
                        }}
                        onFolderDragStart={(e) => {
                          const payload: PathlyFolderDragItem = {
                            dragType: 'reorg-folder',
                            name: subdir.name,
                            sourcePath: folderKey,
                            sectionDir: sectionTargetDir,
                          }
                          e.dataTransfer.setData(PATHLY_DRAG_MIME, JSON.stringify(payload))
                          e.dataTransfer.effectAllowed = 'move'
                        }}
                      />
                      {subdir.open && inlineCreate?.target === folderKey && (
                        <InlineCreateInput
                          type="file"
                          deep
                          onCommit={onInlineCreateSubmit}
                          onCancel={onInlineCreateCancel}
                        />
                      )}
                      {subdir.open && filteredFiles.map((item) => (
                        <WorkspaceItem
                          key={item.path}
                          item={item}
                          itemDir={itemDir}
                          isSelected={selectedItem?.path === item.path}
                          isDirty={dirtyItems.has(item.path)}
                          deep
                          renamingPath={renamingPath}
                          renameValue={renameValue}
                          onSelect={() => onSelect(item)}
                          onRenameChange={onRenameChange}
                          onRenameCommit={() => onRenameCommit(item, itemDir)}
                          onRenameCancel={onRenameCancel}
                          onStartRename={() => onStartRename(item, itemDir)}
                          onStartDelete={() => onStartDelete(item)}
                          sectionId={section.type}
                          isProtectedFile={PROTECTED_FILENAMES.has(item.name)}
                        />
                      ))}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}

      {customWorkspaceSections.map((section) => {
        const state = sections[section.label]
        if (!state) return null
        const subdirs = state.subdirs ?? []
        const hasMatch = !filter || subdirs.some((sd) => sd.files.some((f) => f.name.toLowerCase().includes(lowerFilter)))
        if (!hasMatch && filter) return null
        const sectionTargetDir = `${projectPath}/${section.dir}`
        return (
          <div key={section.label}>
            <SectionHeader
              label={section.label}
              open={state.open}
              onToggle={() => onToggleSection(section.label)}
              alwaysShowActions
              actions={
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 2 }}>
                  {userLockedFolders.has(sectionTargetDir) && (
                    <span className={`${styles.rowAction} ${styles.rowActionLock}`} title="Locked">
                      <Lock size={11} />
                    </span>
                  )}
                  <button
                    className={styles.rowAction}
                    title="Actions"
                    onClick={(e) => { e.stopPropagation(); setCustomSectionMenuOpen(v => v === section.label ? null : section.label) }}
                  >
                    <MoreHorizontal size={13} />
                  </button>
                  {customSectionMenuOpen === section.label && (
                    <div className={styles.itemMenu} ref={customSectionMenuRef}>
                      <button className={styles.itemMenuItem} onClick={(e) => { e.stopPropagation(); setCustomSectionMenuOpen(null); onInlineCreateFolder(section, e) }}>
                        <FolderPlus size={12} />
                        New folder
                      </button>
                      <button className={styles.itemMenuItem} onClick={(e) => { e.stopPropagation(); setCustomSectionMenuOpen(null); onInlineCreateFile(section, e) }}>
                        <FilePlus size={12} />
                        New file
                      </button>
                      <div className={styles.itemMenuSep} />
                      <button className={styles.itemMenuItem} onClick={(e) => { e.stopPropagation(); setCustomSectionMenuOpen(null); toggleFolderLock(sectionTargetDir) }}>
                        <Lock size={12} />
                        {userLockedFolders.has(sectionTargetDir) ? 'Unlock section' : 'Lock section'}
                      </button>
                      {!userLockedFolders.has(sectionTargetDir) && (
                        <>
                          <div className={styles.itemMenuSep} />
                          <button className={`${styles.itemMenuItem} ${styles.itemMenuItemDelete}`} onClick={(e) => { e.stopPropagation(); setCustomSectionMenuOpen(null); onDeleteCustomSection?.(section.dir) }}>
                            <Trash2 size={12} />
                            Delete section
                          </button>
                        </>
                      )}
                    </div>
                  )}
                </div>
              }
            />
            {state.open && (
              <div>
                {inlineCreate?.target === section.dir && (
                  <InlineCreateInput
                    type={inlineCreate.type}
                    onCommit={onInlineCreateSubmit}
                    onCancel={onInlineCreateCancel}
                  />
                )}
                {(state.items ?? []).filter(item => item.name !== '.gitkeep').map((item) => (
                  <WorkspaceItem
                    key={item.path}
                    item={item}
                    itemDir={sectionTargetDir}
                    isSelected={selectedItem?.path === item.path}
                    isDirty={dirtyItems.has(item.path)}
                    renamingPath={renamingPath}
                    renameValue={renameValue}
                    onSelect={() => onSelect(item)}
                    onRenameChange={onRenameChange}
                    onRenameCommit={() => onRenameCommit(item, sectionTargetDir)}
                    onRenameCancel={onRenameCancel}
                    onStartRename={() => onStartRename(item, sectionTargetDir)}
                    onStartDelete={() => onStartDelete(item)}
                    sectionId={section.type}
                    isProtectedFile={PROTECTED_FILENAMES.has(item.name)}
                  />
                ))}
                {subdirs.map((subdir, idx) => {
                  const filteredFiles = filter ? subdir.files.filter((f) => f.name.toLowerCase().includes(lowerFilter)) : subdir.files
                  if (filter && filteredFiles.length === 0) return null
                  const itemDir = `${projectPath}/${section.dir}/${subdir.name}`
                  const folderKey = itemDir
                  return (
                    <div key={subdir.name}>
                      <SubdirRow
                        name={subdir.name}
                        open={subdir.open}
                        onToggle={() => { if (renamingFolderPath !== folderKey) onToggleSubdir(section.label, idx) }}
                        isSystemFolder={subdir.files.some(f => PROTECTED_FILENAMES.has(f.name))}
                        isUserLocked={userLockedFolders.has(folderKey)}
                        onToggleFolderLock={() => toggleFolderLock(folderKey)}
                        isDragOver={dragOverFolder === folderKey}
                        onDragOver={() => setDragOverFolder(folderKey)}
                        onDrop={(e) => { setDragOverFolder(null); e.dataTransfer.getData(PATHLY_DRAG_MIME) }}
                        onDragLeave={() => setDragOverFolder(null)}
                        renamingThis={renamingFolderPath === folderKey}
                        renameValue={renamingFolderValue}
                        onRenameChange={setRenamingFolderValue}
                        onRenameCommit={() => { const v = renamingFolderValue; setRenamingFolderPath(null); onRenameFolder?.(folderKey, v) }}
                        onRenameCancel={() => setRenamingFolderPath(null)}
                        onStartRenameFolder={() => { setRenamingFolderValue(subdir.name); setRenamingFolderPath(folderKey) }}
                        onStartDeleteFolder={!userLockedFolders.has(folderKey) ? () => onDeleteFolder?.(folderKey) : undefined}
                        onCreateFileInFolder={() => {
                          if (!subdir.open) onToggleSubdir(section.label, idx)
                          onInlineCreateFileInFolder?.(folderKey)
                        }}
                        onFolderDragStart={(e) => {
                          const payload = { dragType: 'reorg-folder', name: subdir.name, sourcePath: folderKey, sectionDir: sectionTargetDir }
                          e.dataTransfer.setData(PATHLY_DRAG_MIME, JSON.stringify(payload))
                          e.dataTransfer.effectAllowed = 'move'
                        }}
                      />
                      {subdir.open && inlineCreate?.target === folderKey && (
                        <InlineCreateInput
                          type="file"
                          deep
                          onCommit={onInlineCreateSubmit}
                          onCancel={onInlineCreateCancel}
                        />
                      )}
                      {subdir.open && filteredFiles.map((item) => (
                        <WorkspaceItem
                          key={item.path}
                          item={item}
                          itemDir={itemDir}
                          isSelected={selectedItem?.path === item.path}
                          isDirty={dirtyItems.has(item.path)}
                          deep
                          renamingPath={renamingPath}
                          renameValue={renameValue}
                          onSelect={() => onSelect(item)}
                          onRenameChange={onRenameChange}
                          onRenameCommit={() => onRenameCommit(item, itemDir)}
                          onRenameCancel={onRenameCancel}
                          onStartRename={() => onStartRename(item, itemDir)}
                          onStartDelete={() => onStartDelete(item)}
                          sectionId={section.type}
                          isProtectedFile={PROTECTED_FILENAMES.has(item.name)}
                        />
                      ))}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}
    </>
  )
}
