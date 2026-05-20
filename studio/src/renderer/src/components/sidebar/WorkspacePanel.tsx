import { useState } from 'react'
import { FolderPlus, Plus } from 'lucide-react'
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
  } = props

  const { userLockedFolders, toggleFolderLock } = useUiStore()
  const [dragOverFolder, setDragOverFolder] = useState<string | null>(null)
  const [dragOverSection, setDragOverSection] = useState<string | null>(null)
  const [renamingFolderPath, setRenamingFolderPath] = useState<string | null>(null)
  const [renamingFolderValue, setRenamingFolderValue] = useState('')

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
