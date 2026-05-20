import { useState } from 'react'
import { FolderPlus, Plus } from 'lucide-react'
import type { PathlyItem, SectionState, PathlyReorgDragItem } from '../../types'
import { PATHLY_DRAG_MIME } from '../../types'
import type { PlanFolder } from '../../hooks/usePlanFiles'
import { IconButton } from '../ui'
import { SectionHeader } from './SectionHeader'
import { SubdirRow } from './SubdirRow'
import { WorkspaceItem } from './WorkspaceItem'
import { PlanSection } from './PlanSection'
import { WORKSPACE_FILE_SECTIONS, PROTECTED_FILENAMES } from './constants'
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
  onSelect: (item: PathlyItem) => void
  onToggleSection: (label: string) => void
  onToggleSubdir: (label: string, idx: number) => void
  onActivePanel: (p: 'plan' | 'editor' | 'flow' | 'monitor' | 'settings') => void
  onCreateTopLevelFolder: (e: React.MouseEvent<HTMLButtonElement>) => void
  onInlineCreate: (section: { label: string; type: string; dir: string }, e: React.MouseEvent<HTMLButtonElement>) => void
  onInlineCreateFolder: (section: { label: string; type: string; dir: string }, e: React.MouseEvent<HTMLButtonElement>) => void
  onNewPlan: (e: React.MouseEvent<HTMLButtonElement>) => void
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
}

export function WorkspacePanel(props: Props): JSX.Element {
  const {
    sections, projectPath, selectedItem, dirtyItems,
    filter, lowerFilter, activeTopic, planFolders,
    renamingPath, renameValue,
    onSelect, onToggleSection, onToggleSubdir,
    onCreateTopLevelFolder, onInlineCreate, onInlineCreateFolder, onNewPlan,
    onRenameChange, onRenameCommit, onRenameCancel,
    onStartRename, onStartDelete,
    planOpen, onTogglePlan, onToggleFolder, onFolderClick,
    onReorgDrop,
  } = props

  const { userLockedFolders, toggleFolderLock } = useUiStore()
  const [dragOverFolder, setDragOverFolder] = useState<string | null>(null)

  return (
    <>
      <div className={styles.workspaceHeader}>
        <span className={styles.workspaceHeaderLabel}>WORKSPACE</span>
        <IconButton onClick={onCreateTopLevelFolder} title="New folder in workspace root">
          <FolderPlus size={12} />
        </IconButton>
      </div>

      <PlanSection
        planFolders={planFolders}
        selectedItem={selectedItem}
        dirtyItems={dirtyItems}
        lowerFilter={lowerFilter}
        activeTopic={activeTopic}
        renamingPath={renamingPath}
        renameValue={renameValue}
        planOpen={planOpen}
        onTogglePlan={onTogglePlan}
        onToggleFolder={onToggleFolder}
        onFolderClick={onFolderClick}
        onNewPlan={onNewPlan}
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
        return (
          <div key={section.label}>
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
                  onClick={(e) => onInlineCreate(section, e)}
                  title={`New ${section.label.slice(0, -1).toLowerCase()}`}
                >
                  <Plus size={12} />
                </IconButton>
              }
            />
            {state.open && (
              <div>
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
                        onToggle={() => onToggleSubdir(section.label, idx)}
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
                            if (payload.section !== section.type) return
                            onReorgDrop?.(payload.sourcePath, `${projectPath}/${section.dir}/${subdir.name}`, section.type)
                          } catch { /* ignore malformed payload */ }
                        }}
                        onDragLeave={() => setDragOverFolder(null)}
                      />
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
